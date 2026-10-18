from datetime import datetime, timedelta

import numpy as np
import pytest

from mythicull import db, embed
from tests.conftest import FakeEmbedder, make_jpeg
from tests.test_import import client, run_import, wait  # noqa: F401


@pytest.fixture
def burst(client, tmp_path, monkeypatch):
    """10-frame burst (1 s apart), then a different-looking frame 5 s later, then one 60 s later, in one chapter."""
    root = tmp_path / "shoot"
    t0 = datetime(2025, 6, 14, 14, 0, 0)
    times = [t0 + timedelta(seconds=i) for i in range(10)] + [t0 + timedelta(seconds=14), t0 + timedelta(seconds=74)]
    for i, t in enumerate(times):
        make_jpeg(root / f"p{i:02d}.jpg", t, color=(i * 20, 90, 100))
    pid, job = run_import(client, root)
    assert wait(client, job)["status"] == "done"
    monkeypatch.setattr(embed, "_embedder", FakeEmbedder())

    conn = db.connect()
    rows = conn.execute("SELECT id FROM photos WHERE project_id = ? ORDER BY capture_time", (pid,)).fetchall()
    ids = [r["id"] for r in rows]
    vecs = np.zeros((12, 768), dtype=np.float32)
    vecs[:10, 0] = 1  # burst: near-identical
    vecs[:10, 1] = np.linspace(0, 0.05, 10)
    vecs[10, 2] = 1  # different content, within 10 s
    vecs[11, 0] = 1  # same content as the burst but 60 s later
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    embed.append_store(pid, FakeEmbedder.model_id, ids, vecs)
    sharp = [1.0] * 12
    sharp[6] = 9.0  # sharpest burst frame
    with conn:
        for i, s in zip(ids, sharp):
            conn.execute("UPDATE photos SET sharpness = ? WHERE id = ?", (s, i))
    yield pid, ids
    monkeypatch.setattr(embed, "_embedder", None)


def _groups(client, pid):
    photos = client.get(f"/api/projects/{pid}/photos").json()
    by: dict[str, list[dict]] = {}
    for p in photos:
        by.setdefault(p["group_id"], []).append(p)
    return list(by.values())


def test_burst_collapses_to_one_group_with_sharpest_pick(client, burst):
    pid, ids = burst
    assert client.patch(f"/api/projects/{pid}", json={"dup_threshold": 0.92}).status_code == 200
    groups = _groups(client, pid)
    assert sorted(len(g) for g in groups) == [1, 1, 10]
    big = next(g for g in groups if len(g) == 10)
    assert [p["id"] for p in big if p["is_group_pick"]] == [ids[6]]
    assert all(len(g) != 1 or g[0]["is_group_pick"] for g in groups)


def test_threshold_change_regroups(client, burst):
    pid, _ = burst
    client.patch(f"/api/projects/{pid}", json={"dup_threshold": 0.92})
    client.patch(f"/api/projects/{pid}", json={"dup_threshold": 1.0})
    assert len(_groups(client, pid)) == 12


def test_regroup_keeps_decisions(client, burst):
    pid, ids = burst
    conn = db.connect()
    conn.execute("INSERT INTO decisions (photo_id, status, stars, updated_at) VALUES (?, 'keep', 4, 'x')", (ids[0],))
    conn.commit()
    client.patch(f"/api/projects/{pid}", json={"dup_threshold": 0.5})
    d = conn.execute("SELECT status, stars FROM decisions WHERE photo_id = ?", (ids[0],)).fetchone()
    assert (d["status"], d["stars"]) == ("keep", 4)


def test_unindexed_photos_are_singletons(client, burst, monkeypatch):
    pid, _ = burst
    monkeypatch.setattr(embed, "_embedder", type("Other", (FakeEmbedder,), {"model_id": "other/model"})())
    client.patch(f"/api/projects/{pid}", json={"dup_threshold": 0.92})
    assert len(_groups(client, pid)) == 12
