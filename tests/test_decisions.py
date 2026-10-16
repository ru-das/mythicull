import pytest

from mythicull import embed, grouping, db, ingest, jobs
from tests.test_groups import burst  # noqa: F401
from tests.test_import import client, wait  # noqa: F401


def photo(client, pid, photo_id):
    return next(p for p in client.get(f"/api/projects/{pid}/photos").json() if p["id"] == photo_id)


def test_default_is_undecided(client, burst):  # noqa: F811
    pid, ids = burst
    assert photo(client, pid, ids[0])["status"] is None
    assert photo(client, pid, ids[0])["stars"] == 0


def test_put_sets_and_replaces(client, burst):  # noqa: F811
    pid, ids = burst
    r = client.put(f"/api/photos/{ids[0]}/decision", json={"status": "keep", "stars": 3})
    assert r.json() == {"photo_id": ids[0], "status": "keep", "stars": 3}
    assert (photo(client, pid, ids[0])["status"], photo(client, pid, ids[0])["stars"]) == ("keep", 3)
    client.put(f"/api/photos/{ids[0]}/decision", json={"status": "reject"})
    assert (photo(client, pid, ids[0])["status"], photo(client, pid, ids[0])["stars"]) == ("reject", 0)
    client.put(f"/api/photos/{ids[0]}/decision", json={})
    assert photo(client, pid, ids[0])["status"] is None


def test_put_validates(client, burst):  # noqa: F811
    _, ids = burst
    assert client.put(f"/api/photos/{ids[0]}/decision", json={"stars": 6}).status_code == 422
    assert client.put(f"/api/photos/{ids[0]}/decision", json={"status": "maybe"}).status_code == 422
    assert client.put("/api/photos/nope/decision", json={}).status_code == 404


def test_decisions_survive_reimport_reindex_regroup(client, burst):  # noqa: F811
    pid, ids = burst
    client.put(f"/api/photos/{ids[2]}/decision", json={"status": "keep", "stars": 5})
    client.put(f"/api/photos/{ids[6]}/decision", json={"status": "reject", "stars": 1})
    job = jobs.start("import", lambda ctx: ingest.import_project(ctx, pid), pid)
    assert wait(client, job)["status"] == "done"
    job = jobs.start("index", lambda ctx: embed.index_project(ctx, pid), pid)
    assert wait(client, job)["status"] == "done"
    client.patch(f"/api/projects/{pid}", json={"dup_threshold": 0.5})
    client.patch(f"/api/projects/{pid}", json={"chapter_gap_minutes": 1})
    conn = db.connect()
    grouping.regroup(conn, pid)
    conn.close()
    a, b = photo(client, pid, ids[2]), photo(client, pid, ids[6])
    assert (a["status"], a["stars"]) == ("keep", 5)
    assert (b["status"], b["stars"]) == ("reject", 1)


def test_chapter_kept_and_rejected_counts(client, burst):  # noqa: F811
    pid, ids = burst
    client.put(f"/api/photos/{ids[0]}/decision", json={"status": "keep"})
    client.put(f"/api/photos/{ids[1]}/decision", json={"status": "keep", "stars": 2})
    client.put(f"/api/photos/{ids[2]}/decision", json={"status": "reject"})
    chapters = client.get(f"/api/projects/{pid}/chapters").json()
    assert sum(c["kept_count"] for c in chapters) == 2
    assert sum(c["rejected_count"] for c in chapters) == 1
    client.put(f"/api/photos/{ids[0]}/decision", json={})
    assert sum(c["kept_count"] for c in client.get(f"/api/projects/{pid}/chapters").json()) == 1
