import os
import shutil
import time

import pytest
from fastapi.testclient import TestClient

from mythicull import db
from mythicull.main import app


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("MYTHICULL_DATA_DIR", str(tmp_path / "data"))
    with TestClient(app) as c:
        yield c


def run_import(client, folder, name="shoot"):
    r = client.post("/api/projects", json={"name": name, "folder": str(folder)})
    assert r.status_code == 200
    return r.json()["project"]["id"], r.json()["job_id"]


def wait(client, job_id):
    for _ in range(200):
        j = client.get(f"/api/jobs/{job_id}").json()
        if j["status"] in ("done", "failed", "cancelled"):
            return j
        time.sleep(0.02)
    raise AssertionError("job timeout")


def test_import_twice_keeps_counts_and_decisions(client, photo_folder):
    (photo_folder / "notes.txt").write_text("x")
    pid, job = run_import(client, photo_folder)
    assert wait(client, job)["status"] == "done"
    p = client.get(f"/api/projects/{pid}").json()
    assert p["photo_count"] == 6
    s = p["last_import"]
    assert (s["found"], s["imported"], s["already_present"]) == (6, 6, 0)
    assert s["skipped"][0]["reason"] == "unsupported extension"

    conn = db.connect()
    ids = [r["id"] for r in conn.execute("SELECT id FROM photos ORDER BY path")]
    conn.execute("INSERT INTO decisions (photo_id, status, stars, updated_at) VALUES (?, 'keep', 4, 'now')", (ids[0],))
    conn.commit()
    thumbs = [r["thumb_path"] for r in conn.execute("SELECT thumb_path FROM photos")]
    mt = {t: os.stat(t).st_mtime_ns for t in thumbs}

    # new file appears; re-import through a second project call on same folder is a new project,
    # so re-run the job body directly on the same project
    shutil.copy(photo_folder / "a.jpg", photo_folder / "new.jpg")
    from mythicull import ingest, jobs

    job2 = jobs.start("import", lambda ctx: ingest.import_project(ctx, pid), pid)
    assert wait(client, job2)["status"] == "done"
    s = client.get(f"/api/projects/{pid}").json()
    assert s["photo_count"] == 7
    assert (s["last_import"]["imported"], s["last_import"]["already_present"]) == (1, 6)
    assert [r["id"] for r in conn.execute("SELECT id FROM photos WHERE path NOT LIKE '%new.jpg' ORDER BY path")] == ids
    d = conn.execute("SELECT status, stars FROM decisions").fetchall()
    assert [(r["status"], r["stars"]) for r in d] == [("keep", 4)]
    assert {t: os.stat(t).st_mtime_ns for t in thumbs} == mt


def test_broken_file_skipped_with_reason(client, photo_folder):
    (photo_folder / "bad.nef").write_bytes(b"not a raw")
    pid, job = run_import(client, photo_folder)
    j = wait(client, job)
    assert j["status"] == "done"
    p = client.get(f"/api/projects/{pid}").json()
    assert p["photo_count"] == 6
    assert [s["path"].endswith("bad.nef") for s in p["last_import"]["skipped"]] == [True]
    assert any(f["item"].endswith("bad.nef") for f in j["failures"])


def test_project_validation_and_list(client, photo_folder, tmp_path):
    assert client.post("/api/projects", json={"name": "x", "folder": str(tmp_path / "nope")}).status_code == 400
    assert client.post("/api/projects", json={"name": " ", "folder": str(photo_folder)}).status_code == 400
    assert client.get("/api/projects/nope").status_code == 404
    pid, job = run_import(client, photo_folder)
    wait(client, job)
    assert [p["id"] for p in client.get("/api/projects").json()] == [pid]


def test_originals_untouched(client, photo_folder):
    before = sorted((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in photo_folder.rglob("*") if p.is_file())
    _, job = run_import(client, photo_folder)
    wait(client, job)
    after = sorted((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in photo_folder.rglob("*") if p.is_file())
    assert before == after


def test_photo_list_and_images(client, photo_folder):
    pid, job = run_import(client, photo_folder)
    assert wait(client, job)["status"] == "done"
    photos = client.get(f"/api/projects/{pid}/photos").json()
    assert len(photos) == 6
    times = [p["capture_time"] for p in photos]
    assert times == sorted(times)
    for kind in ("thumb", "preview"):
        r = client.get(f"/api/photos/{photos[0]['id']}/{kind}")
        assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert client.get("/api/photos/nope/thumb").status_code == 404
    assert client.get("/api/projects/nope/photos").status_code == 404
