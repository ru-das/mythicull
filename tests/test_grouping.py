from datetime import datetime, timedelta

from mythicull.grouping import chapter_title, split_chapters
from tests.test_import import client, run_import, wait  # noqa: F401 (client is a fixture)

T0 = datetime(2025, 6, 14, 17, 0)


def times(*minutes: float) -> list[datetime]:
    return [T0 + timedelta(minutes=m) for m in minutes]


def test_split_on_gap_over_threshold_only():
    # exactly 15 min is not a split; 16 is
    t = times(0, 1, 2, 17, 18, 19, 35, 36, 37)
    assert split_chapters(t, 15) == [[0, 1, 2, 3, 4, 5], [6, 7, 8]]
    assert split_chapters(times(0, 1, 2, 18, 19, 20), 15) == [[0, 1, 2], [3, 4, 5]]


def test_small_chapter_merges_into_nearest_in_time():
    # pair at 40-41 is 36 min after the first chapter and 60 min before the last: merges backwards
    t = times(0, 1, 2, 3, 4, 40, 41, 101, 102, 103)
    assert split_chapters(t, 15) == [[0, 1, 2, 3, 4, 5, 6], [7, 8, 9]]
    # pair is closer to the next chapter: merges forwards
    t = times(0, 1, 2, 60, 61, 80, 81, 82)
    assert split_chapters(t, 15) == [[0, 1, 2], [3, 4, 5, 6, 7]]


def test_few_photos_stay_one_chapter_and_empty():
    assert split_chapters(times(0, 120), 15) == [[0, 1]]
    assert split_chapters([], 15) == []


def test_title_format():
    assert chapter_title(2, datetime(2025, 1, 1, 17, 2), datetime(2025, 1, 1, 17, 41)) == "Chapter 2 · 5:02 PM to 5:41 PM"
    assert chapter_title(1, datetime(2025, 1, 1, 0, 5), datetime(2025, 1, 1, 12, 0)) == "Chapter 1 · 12:05 AM to 12:00 PM"


def test_api_chapters_rename_survives_gap_change(client, photo_folder):  # noqa: F811
    pid, job = run_import(client, photo_folder)
    assert wait(client, job)["status"] == "done"
    ch = client.get(f"/api/projects/{pid}/chapters").json()
    assert [c["photo_count"] for c in ch] == [3, 3]
    assert ch[0]["title"] == ch[0]["auto_title"]
    assert ch[0]["auto_title"].startswith("Chapter 1 · ")

    assert len(client.get(f"/api/projects/{pid}/photos", params={"chapter": ch[1]["id"]}).json()) == 3

    r = client.patch(f"/api/chapters/{ch[1]['id']}", json={"user_title": "  First dance "})
    assert r.json()["title"] == "First dance"

    from mythicull import db

    conn = db.connect()
    conn.execute("INSERT INTO decisions (photo_id, status, stars, updated_at) SELECT id, 'keep', 3, 'now' FROM photos LIMIT 1")
    conn.commit()

    p = client.patch(f"/api/projects/{pid}", json={"chapter_gap_minutes": 120}).json()
    assert p["chapter_gap_minutes"] == 120
    ch = client.get(f"/api/projects/{pid}/chapters").json()
    assert [(c["photo_count"], c["title"]) for c in ch] == [(6, "First dance")]
    assert conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 1

    # blank rename reverts to the auto title
    r = client.patch(f"/api/chapters/{ch[0]['id']}", json={"user_title": " "}).json()
    assert r["user_title"] is None and r["title"] == r["auto_title"]

    assert client.patch("/api/chapters/nope", json={"user_title": "x"}).status_code == 404
    assert client.patch(f"/api/projects/{pid}", json={"chapter_gap_minutes": 0}).status_code == 422
    assert client.get("/api/projects/nope/chapters").status_code == 404
