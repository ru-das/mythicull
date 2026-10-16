from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import json
import uuid
from datetime import datetime, timezone

from mythicull import db, ingest, jobs


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    conn = db.connect()
    jobs.mark_interrupted(conn)
    conn.close()
    yield


app = FastAPI(title="MythiCull", lifespan=lifespan)


class Failure(BaseModel):
    item: str | None
    error: str


class JobOut(BaseModel):
    id: str
    project_id: str | None
    kind: str
    status: str
    stage: str | None
    done: int
    total: int
    failures: list[Failure]
    cancel_requested: bool
    created_at: str
    updated_at: str


def _job_or_404(job_id: str, cancel: bool = False) -> JobOut:
    conn = db.connect()
    try:
        if cancel:
            jobs.cancel(conn, job_id)
        job = jobs.get(conn, job_id)
    finally:
        conn.close()
    if job is None:
        raise HTTPException(404, "job not found")
    return JobOut(**job)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> JobOut:
    return _job_or_404(job_id)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> JobOut:
    return _job_or_404(job_id, cancel=True)


class SkippedFile(BaseModel):
    path: str
    reason: str


class ImportSummary(BaseModel):
    found: int
    imported: int
    already_present: int
    skipped: list[SkippedFile]


class ProjectIn(BaseModel):
    name: str
    folder: str


class ProjectOut(BaseModel):
    id: str
    name: str
    folder: str
    created_at: str
    chapter_gap_minutes: int
    dup_threshold: float
    vibe_prompt: str | None
    photo_count: int
    last_import: ImportSummary | None


class ProjectCreatedOut(BaseModel):
    project: ProjectOut
    job_id: str


_PROJECT_SQL = (
    "SELECT p.*, (SELECT COUNT(*) FROM photos WHERE project_id = p.id) AS photo_count FROM projects p"
)


def _project_out(row: object) -> ProjectOut:
    d = dict(row)  # type: ignore[call-overload]
    d["last_import"] = json.loads(d["last_import"]) if d["last_import"] else None
    return ProjectOut(**d)


@app.post("/api/projects")
def create_project(body: ProjectIn) -> ProjectCreatedOut:
    folder = Path(body.folder).expanduser()
    if not body.name.strip():
        raise HTTPException(400, "name is required")
    if not folder.is_dir():
        raise HTTPException(400, f"folder not found: {folder}")
    project_id = uuid.uuid4().hex
    conn = db.connect()
    try:
        with conn:
            conn.execute(
                "INSERT INTO projects (id, name, folder, created_at) VALUES (?, ?, ?, ?)",
                (project_id, body.name.strip(), str(folder), datetime.now(timezone.utc).isoformat()),
            )
        project = _project_out(conn.execute(_PROJECT_SQL + " WHERE p.id = ?", (project_id,)).fetchone())
    finally:
        conn.close()
    job_id = jobs.start("import", lambda ctx: ingest.import_project(ctx, project_id), project_id)
    return ProjectCreatedOut(project=project, job_id=job_id)


@app.get("/api/projects")
def list_projects() -> list[ProjectOut]:
    conn = db.connect()
    try:
        return [_project_out(r) for r in conn.execute(_PROJECT_SQL + " ORDER BY p.created_at DESC")]
    finally:
        conn.close()


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> ProjectOut:
    conn = db.connect()
    try:
        row = conn.execute(_PROJECT_SQL + " WHERE p.id = ?", (project_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(404, "project not found")
    return _project_out(row)


class PhotoOut(BaseModel):
    id: str
    filename: str
    capture_time: str | None
    time_source: str | None
    width: int | None
    height: int | None


@app.get("/api/projects/{project_id}/photos")
def list_photos(project_id: str) -> list[PhotoOut]:
    conn = db.connect()
    try:
        if conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone() is None:
            raise HTTPException(404, "project not found")
        rows = conn.execute(
            "SELECT id, filename, capture_time, time_source, width, height FROM photos"
            " WHERE project_id = ? ORDER BY capture_time, filename",
            (project_id,),
        ).fetchall()
    finally:
        conn.close()
    return [PhotoOut(**dict(r)) for r in rows]


def _photo_image(photo_id: str, column: str) -> FileResponse:
    conn = db.connect()
    try:
        row = conn.execute(f"SELECT {column} AS p FROM photos WHERE id = ?", (photo_id,)).fetchone()  # column is a literal
    finally:
        conn.close()
    if row is None or not row["p"] or not Path(row["p"]).is_file():
        raise HTTPException(404, "image not found")
    return FileResponse(row["p"], media_type="image/jpeg", headers={"Cache-Control": "max-age=31536000, immutable"})


@app.get("/api/photos/{photo_id}/thumb")
def photo_thumb(photo_id: str) -> FileResponse:
    return _photo_image(photo_id, "thumb_path")


@app.get("/api/photos/{photo_id}/preview")
def photo_preview(photo_id: str) -> FileResponse:
    return _photo_image(photo_id, "preview_path")


class HealthOut(BaseModel):
    status: str


@app.get("/api/health")
def health() -> HealthOut:
    return HealthOut(status="ok")


# Mounted last so /api routes added above take precedence.
app.mount("/", StaticFiles(directory=Path(__file__).parent.parent / "web", html=True), name="web")
