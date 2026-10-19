from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import json
import uuid
from datetime import datetime, timezone

from mythicull import config, db, embed, export, folders, grouping, ingest, jobs, search


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    conn = db.connect()
    jobs.mark_interrupted(conn)
    conn.close()
    yield


app = FastAPI(title="MythiCull", lifespan=lifespan)


class FolderChoiceIn(BaseModel):
    purpose: Literal["import", "export"]


class FolderChoiceOut(BaseModel):
    folder: str | None


@app.post("/api/folders/choose")
def choose_folder(body: FolderChoiceIn, request: Request) -> FolderChoiceOut:
    # Only the local app may open desktop windows; reject cross-site requests too.
    if (request.url.hostname not in {"localhost", "127.0.0.1", "::1"}
            or not request.client
            or request.client.host not in {"127.0.0.1", "::1"}
            or request.headers.get("origin") != str(request.base_url).rstrip("/")):
        raise HTTPException(403, "Open MythiCull on localhost to choose a folder on this computer.")
    try:
        return FolderChoiceOut(folder=folders.choose_folder(body.purpose))
    except BlockingIOError as exc:
        raise HTTPException(409, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


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
    vibe_weight: float
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


class ProjectPatch(BaseModel):
    chapter_gap_minutes: int | None = Field(default=None, ge=1)
    dup_threshold: float | None = Field(default=None, ge=0, le=1)
    vibe_prompt: str | None = None  # null or blank clears it
    vibe_weight: float | None = Field(default=None, ge=0, le=1)


@app.patch("/api/projects/{project_id}")
def patch_project(project_id: str, body: ProjectPatch) -> ProjectOut:
    conn = db.connect()
    try:
        if conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone() is None:
            raise HTTPException(404, "project not found")
        vibe_changed = "vibe_prompt" in body.model_fields_set or body.vibe_weight is not None
        if "vibe_prompt" in body.model_fields_set:
            prompt = (body.vibe_prompt or "").strip() or None
            try:  # encode first so a model failure saves nothing
                grouping.save_vibe_vector(project_id, embed.get_embedder(), prompt)
            except Exception as e:
                raise HTTPException(503, f"vibe unavailable: {e}") from e
            with conn:
                conn.execute("UPDATE projects SET vibe_prompt = ? WHERE id = ?", (prompt, project_id))
        if body.vibe_weight is not None:
            with conn:
                conn.execute("UPDATE projects SET vibe_weight = ? WHERE id = ?", (body.vibe_weight, project_id))
        if body.dup_threshold is not None:
            with conn:
                conn.execute("UPDATE projects SET dup_threshold = ? WHERE id = ?", (body.dup_threshold, project_id))
        if body.chapter_gap_minutes is not None:
            with conn:
                conn.execute("UPDATE projects SET chapter_gap_minutes = ? WHERE id = ?", (body.chapter_gap_minutes, project_id))
            grouping.regenerate_chapters(conn, project_id)  # also regroups
        elif body.dup_threshold is not None or vibe_changed:
            grouping.regroup(conn, project_id)
        return _project_out(conn.execute(_PROJECT_SQL + " WHERE p.id = ?", (project_id,)).fetchone())
    finally:
        conn.close()


class ChapterOut(BaseModel):
    id: str
    position: int
    start_time: str
    end_time: str
    auto_title: str
    user_title: str | None
    title: str
    suggested_title: str | None = None
    photo_count: int
    kept_count: int
    rejected_count: int


class ChapterPatch(BaseModel):
    user_title: str | None = None


_CHAPTER_SQL = (
    "SELECT c.*, (SELECT COUNT(*) FROM photos WHERE chapter_id = c.id) AS photo_count,"
    " (SELECT COUNT(*) FROM photos p JOIN decisions d ON d.photo_id = p.id WHERE p.chapter_id = c.id AND d.status = 'keep') AS kept_count,"
    " (SELECT COUNT(*) FROM photos p JOIN decisions d ON d.photo_id = p.id WHERE p.chapter_id = c.id AND d.status = 'reject') AS rejected_count"
    " FROM chapters c"
)


def _chapter_out(row: object, suggested: str | None = None) -> ChapterOut:
    d = dict(row)  # type: ignore[call-overload]
    return ChapterOut(**d, title=d["user_title"] or d["auto_title"], suggested_title=suggested)


@app.get("/api/projects/{project_id}/chapters")
def list_chapters(project_id: str) -> list[ChapterOut]:
    conn = db.connect()
    try:
        if conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone() is None:
            raise HTTPException(404, "project not found")
        suggestions = grouping.chapter_suggestions(conn, project_id)
        return [
            _chapter_out(r, suggestions.get(r["id"]))
            for r in conn.execute(_CHAPTER_SQL + " WHERE c.project_id = ? ORDER BY c.position", (project_id,))
        ]
    finally:
        conn.close()


@app.patch("/api/chapters/{chapter_id}")
def rename_chapter(chapter_id: str, body: ChapterPatch) -> ChapterOut:
    title = (body.user_title or "").strip() or None
    conn = db.connect()
    try:
        with conn:
            cur = conn.execute("UPDATE chapters SET user_title = ? WHERE id = ?", (title, chapter_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "chapter not found")
        return _chapter_out(conn.execute(_CHAPTER_SQL + " WHERE c.id = ?", (chapter_id,)).fetchone())
    finally:
        conn.close()


class JobStartedOut(BaseModel):
    job_id: str


@app.post("/api/projects/{project_id}/index")
def start_index(project_id: str) -> JobStartedOut:
    conn = db.connect()
    try:
        if conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone() is None:
            raise HTTPException(404, "project not found")
        busy = conn.execute(
            "SELECT 1 FROM jobs WHERE project_id = ? AND kind = 'index' AND status IN (?, ?)", (project_id, *jobs.ACTIVE)
        ).fetchone()
    finally:
        conn.close()
    if busy:
        raise HTTPException(409, "an index job is already running for this project")
    return JobStartedOut(job_id=jobs.start("index", lambda ctx: embed.index_project(ctx, project_id), project_id))


@app.post("/api/projects/{project_id}/export/xmp")
def start_export_xmp(project_id: str) -> JobStartedOut:
    conn = db.connect()
    try:
        _require_project(conn, project_id)
    finally:
        conn.close()
    return JobStartedOut(job_id=jobs.start("export_xmp", lambda ctx: export.export_xmp(ctx, project_id), project_id))


class CopyExportIn(BaseModel):
    destination: str
    per_chapter: bool = False


@app.post("/api/projects/{project_id}/export/copy")
def start_export_copy(project_id: str, body: CopyExportIn) -> JobStartedOut:
    conn = db.connect()
    try:
        _require_project(conn, project_id)
        folder = conn.execute("SELECT folder FROM projects WHERE id = ?", (project_id,)).fetchone()["folder"]
    finally:
        conn.close()
    if not body.destination.strip():
        raise HTTPException(400, "destination required")
    dest = Path(body.destination).expanduser().resolve()
    if dest.exists() and not dest.is_dir():
        raise HTTPException(400, f"destination is not a folder: {dest}")
    if dest.is_relative_to(Path(folder).resolve()):
        raise HTTPException(400, "destination must be outside the photo folder")
    return JobStartedOut(
        job_id=jobs.start("export_copy", lambda ctx: export.export_copy(ctx, project_id, dest, body.per_chapter), project_id)
    )


class PhotoOut(BaseModel):
    id: str
    filename: str
    capture_time: str | None
    time_source: str | None
    width: int | None
    height: int | None
    chapter_id: str | None
    group_id: str | None
    is_group_pick: bool
    status: str | None
    stars: int


_PHOTO_SQL = (
    "SELECT p.id, p.filename, p.capture_time, p.time_source, p.width, p.height, p.chapter_id, p.group_id, p.is_group_pick,"
    " d.status, COALESCE(d.stars, 0) AS stars FROM photos p LEFT JOIN decisions d ON d.photo_id = p.id WHERE p.project_id = ?"
)


def _require_project(conn: object, project_id: str) -> None:
    if conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone() is None:  # type: ignore[attr-defined]
        raise HTTPException(404, "project not found")


@app.get("/api/projects/{project_id}/photos")
def list_photos(project_id: str, chapter: str | None = None) -> list[PhotoOut]:
    conn = db.connect()
    try:
        _require_project(conn, project_id)
        sql = _PHOTO_SQL
        args: list[str] = [project_id]
        if chapter:
            sql += " AND p.chapter_id = ?"
            args.append(chapter)
        rows = conn.execute(sql + f" ORDER BY {db.ADJUSTED_TIME}, p.filename", args).fetchall()
    finally:
        conn.close()
    return [PhotoOut(**dict(r)) for r in rows]


class CameraOut(BaseModel):
    camera_model: str  # "" = photos with no camera model in EXIF
    photo_count: int
    offset_seconds: int


class CameraOffsetIn(BaseModel):
    camera_model: str
    offset_seconds: int = Field(ge=-10**9, le=10**9)


def _cameras(conn: object, project_id: str) -> list[CameraOut]:
    rows = conn.execute(  # type: ignore[attr-defined]
        "SELECT COALESCE(p.camera_model, '') AS camera_model, COUNT(*) AS photo_count,"
        " COALESCE(o.offset_seconds, 0) AS offset_seconds FROM photos p"
        " LEFT JOIN camera_offsets o ON o.project_id = p.project_id AND o.camera_model = COALESCE(p.camera_model, '')"
        " WHERE p.project_id = ? GROUP BY COALESCE(p.camera_model, '') ORDER BY 1",
        (project_id,),
    )
    return [CameraOut(**dict(r)) for r in rows]


@app.get("/api/projects/{project_id}/cameras")
def list_cameras(project_id: str) -> list[CameraOut]:
    conn = db.connect()
    try:
        _require_project(conn, project_id)
        return _cameras(conn, project_id)
    finally:
        conn.close()


@app.put("/api/projects/{project_id}/cameras")
def set_camera_offset(project_id: str, body: CameraOffsetIn) -> list[CameraOut]:
    """Set one camera's clock offset, then rebuild chapters and groups. Stored times and originals are not changed."""
    conn = db.connect()
    try:
        _require_project(conn, project_id)
        if body.camera_model not in {c.camera_model for c in _cameras(conn, project_id)}:
            raise HTTPException(400, "unknown camera for this project")
        with conn:
            conn.execute(
                "INSERT INTO camera_offsets (project_id, camera_model, offset_seconds) VALUES (?,?,?)"
                " ON CONFLICT(project_id, camera_model) DO UPDATE SET offset_seconds = excluded.offset_seconds",
                (project_id, body.camera_model, body.offset_seconds),
            )
        grouping.regenerate_chapters(conn, project_id)  # also regroups
        return _cameras(conn, project_id)
    finally:
        conn.close()


@app.get("/api/projects/{project_id}/search")
def search_photos(
    project_id: str, q: str, k: int = Query(default=config.DEFAULT_SEARCH_K, ge=1, le=500), chapter: str | None = None
) -> list[PhotoOut]:
    """Photos best match first. The ranking is the only meaning of position: scores are not returned."""
    if not q.strip():
        raise HTTPException(400, "query is blank")
    conn = db.connect()
    try:
        _require_project(conn, project_id)
        rows = {
            r["id"]: r
            for r in conn.execute(_PHOTO_SQL + (" AND p.chapter_id = ?" if chapter else ""), [project_id] + ([chapter] if chapter else []))
        }
    finally:
        conn.close()
    try:
        embedder = embed.get_embedder()
        ids = search.rank(project_id, embedder, q.strip(), k, set(rows) if chapter else None)
    except Exception as e:  # e.g. model download blocked; browsing must keep working
        raise HTTPException(503, f"search unavailable: {e}") from e
    return [PhotoOut(**dict(rows[i])) for i in ids if i in rows]


class DecisionIn(BaseModel):
    status: Literal["keep", "reject"] | None = None
    stars: int = Field(default=0, ge=0, le=5)


class DecisionOut(BaseModel):
    photo_id: str
    status: str | None
    stars: int


@app.put("/api/photos/{photo_id}/decision")
def put_decision(photo_id: str, body: DecisionIn) -> DecisionOut:
    """Replaces the photo's whole decision (status and stars)."""
    conn = db.connect()
    try:
        if conn.execute("SELECT 1 FROM photos WHERE id = ?", (photo_id,)).fetchone() is None:
            raise HTTPException(404, "photo not found")
        with conn:
            conn.execute(
                "INSERT INTO decisions (photo_id, status, stars, updated_at) VALUES (?, ?, ?, ?)"
                " ON CONFLICT(photo_id) DO UPDATE SET status = excluded.status, stars = excluded.stars, updated_at = excluded.updated_at",
                (photo_id, body.status, body.stars, datetime.now(timezone.utc).isoformat()),
            )
    finally:
        conn.close()
    return DecisionOut(photo_id=photo_id, status=body.status, stars=body.stars)


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


class ModelOut(BaseModel):
    ready: bool
    path: str


@app.get("/api/model")
def model_status() -> ModelOut:
    return ModelOut(ready=embed.model_ready(), path=str(config.model_dir()))


@app.post("/api/model/download")
def download_model() -> JobStartedOut:
    return JobStartedOut(job_id=jobs.start("model_download", embed.download_model))


@app.get("/api/health")
def health() -> HealthOut:
    return HealthOut(status="ok")


# Mounted last so /api routes added above take precedence.
app.mount("/", StaticFiles(directory=Path(__file__).parent.parent / "web", html=True), name="web")
