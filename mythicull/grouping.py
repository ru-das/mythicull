import sqlite3
import uuid
from datetime import datetime

import numpy as np

from mythicull import embed

MIN_CHAPTER_PHOTOS = 3
DUP_WINDOW_SECONDS = 10


def split_chapters(times: list[datetime], gap_minutes: int) -> list[list[int]]:
    """Split time-sorted `times` into chapters of indices. A gap strictly above `gap_minutes` starts a new one;
    chapters under MIN_CHAPTER_PHOTOS then merge into the nearer neighbour in time (tie: the earlier one)."""
    if not times:
        return []
    chapters: list[list[int]] = [[0]]
    for i in range(1, len(times)):
        if (times[i] - times[i - 1]).total_seconds() > gap_minutes * 60:
            chapters.append([])
        chapters[-1].append(i)
    while len(chapters) > 1:
        small = next((k for k, c in enumerate(chapters) if len(c) < MIN_CHAPTER_PHOTOS), None)
        if small is None:
            break
        gap_prev = (times[chapters[small][0]] - times[chapters[small - 1][-1]]).total_seconds() if small > 0 else None
        gap_next = (times[chapters[small + 1][0]] - times[chapters[small][-1]]).total_seconds() if small + 1 < len(chapters) else None
        into_prev = gap_next is None or (gap_prev is not None and gap_prev <= gap_next)
        if into_prev:
            chapters[small - 1].extend(chapters.pop(small))
        else:
            chapters[small] = chapters.pop(small) + chapters[small]  # after the pop, the next chapter sits at `small`
    return chapters


def _clock(t: datetime) -> str:
    return f"{t.hour % 12 or 12}:{t.minute:02d} {'AM' if t.hour < 12 else 'PM'}"


def chapter_title(n: int, start: datetime, end: datetime) -> str:
    return f"Chapter {n} · {_clock(start)} to {_clock(end)}"


def regenerate_chapters(conn: sqlite3.Connection, project_id: str) -> None:
    """Rebuild a project's chapters from capture times. User-renamed titles move to the new chapter with the
    largest photo overlap. Photo decisions are not touched."""
    photos = [
        r for r in conn.execute(
            "SELECT id, capture_time, chapter_id FROM photos WHERE project_id = ? AND capture_time IS NOT NULL"
            " ORDER BY capture_time, filename",
            (project_id,),
        )
    ]
    gap = conn.execute("SELECT chapter_gap_minutes FROM projects WHERE id = ?", (project_id,)).fetchone()[0]
    times = [datetime.fromisoformat(p["capture_time"]) for p in photos]
    groups = split_chapters(times, gap)

    renamed = {
        r["id"]: r["user_title"]
        for r in conn.execute("SELECT id, user_title FROM chapters WHERE project_id = ? AND user_title IS NOT NULL", (project_id,))
    }
    # Greedy by overlap size: each old title and each new chapter is used at most once.
    overlaps: dict[tuple[str, int], int] = {}
    for k, g in enumerate(groups):
        for i in g:
            old = photos[i]["chapter_id"]
            if old in renamed:
                overlaps[(old, k)] = overlaps.get((old, k), 0) + 1
    titles: dict[int, str] = {}
    used: set[str] = set()
    for (old, k), _ in sorted(overlaps.items(), key=lambda kv: -kv[1]):
        if old not in used and k not in titles:
            used.add(old)
            titles[k] = renamed[old]

    with conn:
        conn.execute("UPDATE photos SET chapter_id = NULL WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM chapters WHERE project_id = ?", (project_id,))
        for k, g in enumerate(groups):
            cid = uuid.uuid4().hex
            start, end = times[g[0]], times[g[-1]]
            conn.execute(
                "INSERT INTO chapters (id, project_id, position, start_time, end_time, auto_title, user_title)"
                " VALUES (?,?,?,?,?,?,?)",
                (cid, project_id, k + 1, photos[g[0]]["capture_time"], photos[g[-1]]["capture_time"],
                 chapter_title(k + 1, start, end), titles.get(k)),
            )
            conn.executemany("UPDATE photos SET chapter_id = ? WHERE id = ?", [(cid, photos[i]["id"]) for i in g])
    regroup(conn, project_id)


def regroup(conn: sqlite3.Connection, project_id: str) -> None:
    """Rebuild duplicate groups. A photo joins the previous photo's group when both are in one chapter, at most
    DUP_WINDOW_SECONDS apart, both embedded, and cosine similarity >= dup_threshold. The sharpest photo is the pick.
    Photo decisions are not touched."""
    threshold = conn.execute("SELECT dup_threshold FROM projects WHERE id = ?", (project_id,)).fetchone()[0]
    ids, matrix = embed.load_store(project_id, embed.get_embedder().model_id)
    row_of = {pid: i for i, pid in enumerate(ids)}
    photos = conn.execute(
        "SELECT id, capture_time, chapter_id, sharpness FROM photos WHERE project_id = ? ORDER BY capture_time, filename",
        (project_id,),
    ).fetchall()

    groups: list[list[sqlite3.Row]] = []
    prev = None
    for p in photos:
        if prev is not None and _same_burst(prev, p, row_of, matrix, threshold):
            groups[-1].append(p)
        else:
            groups.append([p])
        prev = p

    updates = []
    for g in groups:
        gid = uuid.uuid4().hex
        pick = max(g, key=lambda p: -1.0 if p["sharpness"] is None else p["sharpness"])
        updates += [(gid, int(p["id"] == pick["id"]), p["id"]) for p in g]
    with conn:
        conn.executemany("UPDATE photos SET group_id = ?, is_group_pick = ? WHERE id = ?", updates)


def _same_burst(a: sqlite3.Row, b: sqlite3.Row, row_of: dict[str, int], matrix: np.ndarray, threshold: float) -> bool:
    if a["chapter_id"] is None or a["chapter_id"] != b["chapter_id"] or a["id"] not in row_of or b["id"] not in row_of:
        return False
    dt = (datetime.fromisoformat(b["capture_time"]) - datetime.fromisoformat(a["capture_time"])).total_seconds()
    return dt <= DUP_WINDOW_SECONDS and float(matrix[row_of[a["id"]]] @ matrix[row_of[b["id"]]]) >= threshold
