import pytest

from mythicull import db
from tests.test_import import client, wait  # noqa: F401


@pytest.fixture
def shoot(client, tmp_path):  # noqa: F811
    folder = tmp_path / "shoot"
    folder.mkdir()
    conn = db.connect()
    conn.execute("INSERT INTO projects (id, name, folder, created_at) VALUES ('p', 'p', ?, 'now')", (str(folder),))

    def add(name, status=None, stars=0, content=b"raw"):
        path = folder / name
        path.write_bytes(content)
        conn.execute("INSERT INTO photos (id, project_id, path, filename) VALUES (?, 'p', ?, ?)", (name, str(path), name))
        if status or stars:
            conn.execute("INSERT INTO decisions (photo_id, status, stars, updated_at) VALUES (?, ?, ?, 'now')", (name, status, stars))
        return path

    yield folder, add, conn
    conn.close()


def export(client, conn):  # noqa: F811
    conn.commit()
    r = client.post("/api/projects/p/export/xmp")
    assert r.status_code == 200
    return wait(client, r.json()["job_id"])


def test_keep_reject_and_skips(client, shoot):  # noqa: F811
    folder, add, conn = shoot
    add("keep3.CR2", "keep", 3)
    add("keep0.NEF", "keep", 0)
    add("rej.ARW", "reject", 2)
    add("undecided.CR2")
    add("stars_only.CR2", None, 4)
    add("pic.jpg", "keep", 5)
    add("pic.dng", "keep", 5)
    job = export(client, conn)
    assert job["status"] == "done"
    xmp = lambda n: (folder / n).read_text()  # noqa: E731
    assert 'xmp:Rating="3"' in xmp("keep3.xmp") and 'xmp:Label="Green"' in xmp("keep3.xmp")
    assert 'xmp:Rating="1"' in xmp("keep0.xmp")
    assert 'xmp:Rating="0"' in xmp("rej.xmp") and 'xmp:Label="Red"' in xmp("rej.xmp")
    assert 'xmp:CreatorTool="MythiCull"' in xmp("rej.xmp")
    assert sorted(p.name for p in folder.glob("*.xmp")) == ["keep0.xmp", "keep3.xmp", "rej.xmp"]
    assert sorted(f["item"].rsplit("/", 1)[1] for f in job["failures"]) == ["pic.dng", "pic.jpg"]
    assert (folder / "pic.jpg").read_bytes() == b"raw"


def test_foreign_sidecar_skipped_own_updated(client, shoot):  # noqa: F811
    folder, add, conn = shoot
    add("a.CR2", "keep", 2)
    add("b.CR2", "keep", 2)
    (folder / "a.xmp").write_text("<x:xmpmeta>lightroom</x:xmpmeta>")
    (folder / "b.xmp").write_text('<rdf:Description xmp:CreatorTool="MythiCull" xmp:Rating="9"/>')
    job = export(client, conn)
    assert (folder / "a.xmp").read_text() == "<x:xmpmeta>lightroom</x:xmpmeta>"
    assert 'xmp:Rating="2"' in (folder / "b.xmp").read_text()
    assert [f["error"] for f in job["failures"]] == ["existing sidecar not written by MythiCull"]
    assert job["failures"][0]["item"].endswith("a.xmp")


def test_missing_original_and_unknown_project(client, shoot):  # noqa: F811
    folder, add, conn = shoot
    add("gone.CR2", "keep", 1).unlink()
    job = export(client, conn)
    assert job["failures"][0]["error"] == "original file missing"
    assert client.post("/api/projects/nope/export/xmp").status_code == 404
