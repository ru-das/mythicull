import time
from datetime import datetime, timedelta

import numpy as np
import pytest
from PIL import Image, ImageFilter

from mythicull import db, embed, jobs, quality
from tests.conftest import FakeEmbedder, make_jpeg
from tests.test_import import client, run_import, wait  # noqa: F401


def _varied_folder(tmp_path):
    """Distinct pixel content per photo so the fake embedder gives distinct vectors."""
    root = tmp_path / "shoot"
    t0 = datetime(2025, 6, 14, 14, 0, 0)
    for i in range(6):
        make_jpeg(root / f"p{i}.jpg", t0 + timedelta(seconds=i), color=(i * 40, 90, 200 - i * 30))
    return root


@pytest.fixture
def project(client, tmp_path, monkeypatch):
    monkeypatch.setenv("MYTHICULL_BATCH_SIZE", "2")
    pid, job = run_import(client, _varied_folder(tmp_path))
    assert wait(client, job)["status"] == "done"
    yield pid
    monkeypatch.setattr(embed, "_embedder", None)


def _use(monkeypatch, fake):
    monkeypatch.setattr(embed, "_embedder", fake)
    return fake


def _store(pid):
    return embed.load_store(pid, FakeEmbedder.model_id)


def test_index_all(client, project, monkeypatch):
    fake = _use(monkeypatch, FakeEmbedder())
    conn = db.connect()
    pid_photo = conn.execute("SELECT id FROM photos WHERE project_id = ? LIMIT 1", (project,)).fetchone()["id"]
    conn.execute("INSERT INTO decisions (photo_id, status, stars, updated_at) VALUES (?, 'keep', 3, 'x')", (pid_photo,))
    conn.commit()
    job = client.post(f"/api/projects/{project}/index").json()["job_id"]
    j = wait(client, job)
    assert j["status"] == "done" and j["done"] == j["total"] == 6 and not j["failures"]
    ids, m = _store(project)
    assert m.shape == (6, 768) and np.allclose(np.linalg.norm(m, axis=1), 1, atol=1e-5)
    rows = conn.execute("SELECT id, embedded, sharpness FROM photos WHERE project_id = ?", (project,)).fetchall()
    assert set(ids) == {r["id"] for r in rows}
    assert all(r["embedded"] == 1 and r["sharpness"] is not None for r in rows)
    d = conn.execute("SELECT status, stars FROM decisions WHERE photo_id = ?", (pid_photo,)).fetchone()
    assert (d["status"], d["stars"]) == ("keep", 3)
    assert fake.images_seen == 6


def test_resume_after_interruption(client, project, monkeypatch):
    def boom(n):
        if n == 2:
            raise RuntimeError("killed")

    _use(monkeypatch, FakeEmbedder(on_batch=boom))
    j = wait(client, client.post(f"/api/projects/{project}/index").json()["job_id"])
    assert j["status"] == "failed"
    assert len(_store(project)[0]) == 2
    fake = _use(monkeypatch, FakeEmbedder())
    j = wait(client, client.post(f"/api/projects/{project}/index").json()["job_id"])
    assert j["status"] == "done" and j["done"] == 6
    assert fake.images_seen == 4
    ids, m = _store(project)
    assert len(set(ids)) == 6 and m.shape[0] == 6


def test_cancel(client, project, monkeypatch):
    def cancel(n):
        if n == 2:
            conn = db.connect()
            jobs.cancel(conn, conn.execute("SELECT id FROM jobs WHERE kind='index'").fetchone()["id"])

    _use(monkeypatch, FakeEmbedder(on_batch=cancel))
    j = wait(client, client.post(f"/api/projects/{project}/index").json()["job_id"])
    assert j["status"] == "cancelled"
    assert len(_store(project)[0]) == 4  # batch 2 finished, batch 3 never started


def test_second_index_refused_and_404(client, project, monkeypatch):
    release = []
    _use(monkeypatch, FakeEmbedder(on_batch=lambda n: [time.sleep(0.01) for _ in range(300) if not release]))
    job = client.post(f"/api/projects/{project}/index").json()["job_id"]
    assert client.post(f"/api/projects/{project}/index").status_code == 409
    release.append(1)
    wait(client, job)
    assert client.post("/api/projects/nope/index").status_code == 404


def test_store_ignores_extra_rows(client, project, monkeypatch):
    _use(monkeypatch, FakeEmbedder())
    wait(client, client.post(f"/api/projects/{project}/index").json()["job_id"])
    d = embed.project_dir(project)
    np.save(d / "embeddings.npy", np.vstack([np.load(d / "embeddings.npy"), np.ones((1, 768), dtype=np.float32)]))
    ids, m = _store(project)
    assert m.shape[0] == len(ids) == 6
    assert embed.load_store(project, "other/model")[0] == []


def test_sharpness_ranks_blur_lower(tmp_path):
    img = Image.effect_noise((200, 200), 64).convert("RGB")
    img.save(tmp_path / "sharp.jpg")
    img.filter(ImageFilter.GaussianBlur(4)).save(tmp_path / "blur.jpg")
    assert quality.sharpness(tmp_path / "sharp.jpg") > quality.sharpness(tmp_path / "blur.jpg")


@pytest.mark.model
def test_gemma_embeds(tmp_path):
    paths = [make_jpeg(tmp_path / f"{i}.jpg", None, color=(i * 90, 50, 50)) for i in range(2)]
    v = embed.GemmaEmbedder().encode_images([Image.open(p) for p in paths])
    assert v.shape == (2, 768) and not np.isnan(v).any()
