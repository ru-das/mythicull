from datetime import datetime, timedelta

from mythicull import db
from tests.conftest import make_jpeg
from tests.test_import import client, run_import, wait  # noqa: F401 (client is a fixture)


def two_bodies(root):
    """Body A shot 14:00 to 14:02; body B's clock is an hour behind, so its photos read 13:00 to 13:02."""
    t0 = datetime(2025, 6, 14, 14, 0, 0)
    for i in range(3):
        make_jpeg(root / f"a{i}.jpg", t0 + timedelta(seconds=60 * i), model="Body A")
        make_jpeg(root / f"b{i}.jpg", t0 - timedelta(hours=1) + timedelta(seconds=60 * i + 30), model="Body B")
    return root


def test_offset_merges_chapters_and_keeps_user_data(client, tmp_path):  # noqa: F811
    root = two_bodies(tmp_path / "shoot")
    before = {p: p.read_bytes() for p in root.iterdir()}
    pid, job = run_import(client, root)
    assert wait(client, job)["status"] == "done"
    assert [(c["camera_model"], c["photo_count"], c["offset_seconds"]) for c in client.get(f"/api/projects/{pid}/cameras").json()] == [
        ("Body A", 3, 0), ("Body B", 3, 0)]
    ch = client.get(f"/api/projects/{pid}/chapters").json()
    assert len(ch) == 2
    client.patch(f"/api/chapters/{ch[1]['id']}", json={"user_title": "Ceremony"})
    conn = db.connect()
    conn.execute("INSERT INTO decisions (photo_id, status, stars, updated_at) SELECT id, 'keep', 3, 'now' FROM photos LIMIT 1")
    conn.commit()
    raw = {p["filename"]: p["capture_time"] for p in client.get(f"/api/projects/{pid}/photos").json()}

    r = client.put(f"/api/projects/{pid}/cameras", json={"camera_model": "Body B", "offset_seconds": 3600})
    assert r.status_code == 200 and [c["offset_seconds"] for c in r.json()] == [0, 3600]
    ch = client.get(f"/api/projects/{pid}/chapters").json()
    assert [(c["photo_count"], c["title"]) for c in ch] == [(6, "Ceremony")]
    photos = client.get(f"/api/projects/{pid}/photos").json()
    assert [p["filename"] for p in photos] == ["a0.jpg", "b0.jpg", "a1.jpg", "b1.jpg", "a2.jpg", "b2.jpg"]
    assert {p["filename"]: p["capture_time"] for p in photos} == raw  # stored EXIF time is not shifted
    assert conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 1
    assert {p: p.read_bytes() for p in root.iterdir()} == before

    client.put(f"/api/projects/{pid}/cameras", json={"camera_model": "Body B", "offset_seconds": 0})
    assert len(client.get(f"/api/projects/{pid}/chapters").json()) == 2


def test_photos_without_camera_model_use_blank_key(client, photo_folder):  # noqa: F811
    pid, job = run_import(client, photo_folder)
    assert wait(client, job)["status"] == "done"
    assert [c["camera_model"] for c in client.get(f"/api/projects/{pid}/cameras").json()] == [""]
    r = client.put(f"/api/projects/{pid}/cameras", json={"camera_model": "", "offset_seconds": -60})
    assert r.status_code == 200 and r.json()[0]["offset_seconds"] == -60


def test_camera_errors(client, photo_folder):  # noqa: F811
    pid, job = run_import(client, photo_folder)
    wait(client, job)
    assert client.put(f"/api/projects/{pid}/cameras", json={"camera_model": "Nope", "offset_seconds": 1}).status_code == 400
    assert client.put("/api/projects/nope/cameras", json={"camera_model": "", "offset_seconds": 1}).status_code == 404
    assert client.get("/api/projects/nope/cameras").status_code == 404
