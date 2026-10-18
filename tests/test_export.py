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


def copy(client, conn, dest, per_chapter=False):  # noqa: F811
    conn.commit()
    r = client.post("/api/projects/p/export/copy", json={"destination": str(dest), "per_chapter": per_chapter})
    assert r.status_code == 200, r.text
    return wait(client, r.json()["job_id"])


def test_copy_name_clashes_and_pairs(client, shoot, tmp_path):  # noqa: F811
    import json

    folder, add, conn = shoot
    a = add("a.CR2", "keep", 3)
    (folder / "a.JPG").write_bytes(b"jpg")
    conn.execute("UPDATE photos SET companion_path = ? WHERE id = 'a.CR2'", (str(folder / "a.JPG"),))
    (folder / "sub").mkdir()
    x1 = add("x.jpg", "keep", 1, b"one")
    (folder / "sub" / "x.jpg").write_bytes(b"two")
    conn.execute("INSERT INTO photos (id, project_id, path, filename) VALUES ('x2', 'p', ?, 'x.jpg')", (str(folder / "sub" / "x.jpg"),))
    conn.execute("INSERT INTO decisions (photo_id, status, stars, updated_at) VALUES ('x2', 'keep', 2, 'now')")
    add("rej.CR2", "reject", 1)
    add("none.CR2")
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "a.CR2").write_bytes(b"precious")
    job = copy(client, conn, dest)
    assert job["status"] == "done" and not job["failures"]
    assert (dest / "a.CR2").read_bytes() == b"precious"
    assert (dest / "a_1.CR2").read_bytes() == b"raw" and (dest / "a_1.JPG").read_bytes() == b"jpg"
    assert {(dest / n).read_bytes() for n in ("x.jpg", "x_1.jpg")} == {b"one", b"two"}
    assert not (dest / "rej.CR2").exists() and not (dest / "none.CR2").exists()
    assert a.read_bytes() == b"raw" and x1.read_bytes() == b"one"
    m = json.loads((dest / "mythicull_manifest.json").read_text())
    names = [p["filename"] for c in m["chapters"] for p in c["photos"]]
    assert sorted(names) == ["a_1.CR2", "x.jpg", "x_1.jpg"]
    job = copy(client, conn, dest)  # manifest and files never overwritten on a second run
    assert (dest / "mythicull_manifest_1.json").exists() and (dest / "a_2.CR2").exists()


def test_copy_per_chapter_and_missing(client, shoot, tmp_path):  # noqa: F811
    import json

    folder, add, conn = shoot
    for pos, title in ((0, "Ceremony"), (1, "Dance/Floor")):
        conn.execute(
            "INSERT INTO chapters (id, project_id, position, start_time, end_time, auto_title, user_title)"
            " VALUES (?, 'p', ?, 't', 't', ?, NULL)",
            (f"c{pos}", pos, title),
        )
    add("b.CR2", "keep", 4)
    add("a.CR2", "keep", 2)
    add("gone.CR2", "keep", 1).unlink()
    for name, ch, t in (("a.CR2", "c0", "1"), ("b.CR2", "c1", "2"), ("gone.CR2", "c1", "3")):
        conn.execute("UPDATE photos SET chapter_id = ?, capture_time = ? WHERE id = ?", (ch, t, name))
    dest = tmp_path / "out"
    job = copy(client, conn, dest, per_chapter=True)
    assert [f["error"] for f in job["failures"]] == ["original file missing"]
    assert (dest / "01 Ceremony" / "a.CR2").exists() and (dest / "02 DanceFloor" / "b.CR2").exists()
    m = json.loads((dest / "mythicull_manifest.json").read_text())
    assert [(c["title"], c["folder"], [p["stars"] for p in c["photos"]]) for c in m["chapters"]] == [
        ("Ceremony", "01 Ceremony", [2]),
        ("Dance/Floor", "02 DanceFloor", [4]),
    ]


def test_copy_refuses_destination_inside_source(client, shoot):  # noqa: F811
    folder, add, conn = shoot
    add("a.CR2", "keep", 1)
    conn.commit()
    for d in (folder, folder / "out"):
        r = client.post("/api/projects/p/export/copy", json={"destination": str(d)})
        assert r.status_code == 400
    assert not (folder / "out").exists() and not (folder / "mythicull_manifest.json").exists()
    assert client.post("/api/projects/nope/export/copy", json={"destination": "/tmp/x"}).status_code == 404
