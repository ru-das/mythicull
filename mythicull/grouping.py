import os
import sqlite3
import uuid
from datetime import datetime

import numpy as np

from mythicull import config, db, embed

MIN_CHAPTER_PHOTOS = 3
DUP_WINDOW_SECONDS = 10

CHAPTER_LABELS = [
    "getting ready", "details and decor", "ceremony", "vows", "ring exchange", "first kiss",
    "family group photos", "couple portraits", "cocktail hour", "reception entrance", "speeches",
    "first dance", "cake cutting", "dance floor", "keynote", "awards", "audience", "venue exterior",
]


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
            f"SELECT p.id, {db.ADJUSTED_TIME} AS capture_time, p.chapter_id FROM photos p"
            " WHERE p.project_id = ? AND p.capture_time IS NOT NULL ORDER BY 2, p.filename",
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
    threshold, vibe_prompt, vibe_weight = conn.execute(
        "SELECT dup_threshold, vibe_prompt, vibe_weight FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    model_id = embed.get_embedder().model_id
    ids, matrix = embed.load_store(project_id, model_id)
    vibe = _vibe_vector(project_id, vibe_prompt, model_id) if vibe_prompt and vibe_weight > 0 else None
    row_of = {pid: i for i, pid in enumerate(ids)}
    photos = conn.execute(
        f"SELECT p.id, {db.ADJUSTED_TIME} AS capture_time, p.chapter_id, p.sharpness FROM photos p"
        " WHERE p.project_id = ? ORDER BY 2, p.filename",
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
        pick = _pick(g, row_of, matrix, vibe, vibe_weight)
        updates += [(gid, int(p["id"] == pick["id"]), p["id"]) for p in g]
    with conn:
        conn.executemany("UPDATE photos SET group_id = ?, is_group_pick = ? WHERE id = ?", updates)


def _pick(g: list[sqlite3.Row], row_of: dict[str, int], matrix: np.ndarray, vibe: np.ndarray | None, weight: float) -> sqlite3.Row:
    """Sharpest photo, or with a vibe vector the best blend of sharpness rank and vibe rank within the group.
    Ranks only: text-to-image scores are never compared against a fixed number. Ties go to the earliest photo."""
    sharp = lambda p: -1.0 if p["sharpness"] is None else p["sharpness"]  # noqa: E731
    if vibe is None or len(g) == 1:
        return max(g, key=sharp)
    sharp_rank = {p["id"]: r for r, p in enumerate(sorted(g, key=lambda p: -sharp(p)))}
    score = lambda p: float(matrix[row_of[p["id"]]] @ vibe) if p["id"] in row_of else -2.0  # noqa: E731
    vibe_rank = {p["id"]: r for r, p in enumerate(sorted(g, key=lambda p: -score(p)))}
    return min(g, key=lambda p: (1 - weight) * sharp_rank[p["id"]] + weight * vibe_rank[p["id"]])


def _vibe_path(project_id: str):  # noqa: ANN202
    return embed.project_dir(project_id) / "vibe.npz"


def save_vibe_vector(project_id: str, embedder: embed.Embedder, prompt: str | None) -> None:
    """Cache the text embedding of the vibe prompt (this loads the model). `None` removes the cache."""
    path = _vibe_path(project_id)
    if not prompt:
        path.unlink(missing_ok=True)
        return
    vec = embedder.encode_text([prompt])[0].astype(np.float32)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("vibe.tmp.npz")
    np.savez(tmp, model_id=embedder.model_id, prompt=prompt, vector=vec)
    os.replace(tmp, path)


def _vibe_vector(project_id: str, prompt: str, model_id: str) -> np.ndarray | None:
    """Cached vibe vector if it matches the prompt and model. Never loads the model."""
    try:
        with np.load(_vibe_path(project_id)) as f:
            if str(f["model_id"]) == model_id and str(f["prompt"]) == prompt:
                return f["vector"]
    except (FileNotFoundError, ValueError, KeyError):
        pass
    return None


def _same_burst(a: sqlite3.Row, b: sqlite3.Row, row_of: dict[str, int], matrix: np.ndarray, threshold: float) -> bool:
    if a["chapter_id"] is None or a["chapter_id"] != b["chapter_id"] or a["id"] not in row_of or b["id"] not in row_of:
        return False
    dt = (datetime.fromisoformat(b["capture_time"]) - datetime.fromisoformat(a["capture_time"])).total_seconds()
    return dt <= DUP_WINDOW_SECONDS and float(matrix[row_of[a["id"]]] @ matrix[row_of[b["id"]]]) >= threshold


def _labels_path():  # noqa: ANN202
    return config.data_dir() / "chapter_labels.npz"


def save_label_vectors(embedder: embed.Embedder) -> None:
    """Cache text embeddings of CHAPTER_LABELS. Encodes only when the cache is missing or from another model."""
    path = _labels_path()
    try:
        with np.load(path) as f:
            if str(f["model_id"]) == embedder.model_id and list(f["labels"]) == CHAPTER_LABELS:
                return
    except (FileNotFoundError, ValueError, KeyError):
        pass
    tmp = path.with_name("chapter_labels.tmp.npz")
    np.savez(tmp, model_id=embedder.model_id, labels=np.array(CHAPTER_LABELS), vectors=embedder.encode_text(CHAPTER_LABELS).astype(np.float32))
    os.replace(tmp, path)


def chapter_suggestions(conn: sqlite3.Connection, project_id: str) -> dict[str, str]:
    """Best-matching label per chapter (chapter id -> label), from the mean image embedding of its indexed photos.
    Never loads the model: needs the label cache from an index run. Scores are only compared within one chapter."""
    try:
        with np.load(_labels_path()) as f:
            label_model, labels, vectors = str(f["model_id"]), [str(x) for x in f["labels"]], f["vectors"]
    except (FileNotFoundError, ValueError, KeyError):
        return {}
    ids, matrix = embed.load_store(project_id, label_model)
    if not ids:
        return {}
    row_of = {pid: i for i, pid in enumerate(ids)}
    rows_by_chapter: dict[str, list[int]] = {}
    for r in conn.execute("SELECT id, chapter_id FROM photos WHERE project_id = ? AND chapter_id IS NOT NULL", (project_id,)):
        if r["id"] in row_of:
            rows_by_chapter.setdefault(r["chapter_id"], []).append(row_of[r["id"]])
    out = {}
    for cid, rows in rows_by_chapter.items():
        label = labels[int(np.argmax(vectors @ matrix[rows].mean(axis=0)))]
        out[cid] = label[0].upper() + label[1:]
    return out
