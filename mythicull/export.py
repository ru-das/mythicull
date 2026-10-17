import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from mythicull import db, ingest, jobs

CREATOR_MARK = 'xmp:CreatorTool="MythiCull"'


def xmp_text(status: str, stars: int) -> str:
    """Minimal XMP sidecar: keep = stars (min 1) + Green, reject = 0 + Red."""
    rating, label = (max(stars, 1), "Green") if status == "keep" else (0, "Red")
    return (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        '<rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/"\n'
        f' {CREATOR_MARK}\n'
        f' xmp:Rating="{rating}"\n'
        f' xmp:Label="{label}"/>\n'
        "</rdf:RDF>\n"
        "</x:xmpmeta>\n"
        '<?xpacket end="w"?>\n'
    )


def export_xmp(ctx: jobs.JobContext, project_id: str) -> None:
    """Job body: write a sidecar next to each decided RAW. Skips are recorded as job failures."""
    rows = ctx.conn.execute(
        "SELECT p.path, d.status, d.stars FROM photos p JOIN decisions d ON d.photo_id = p.id"
        " WHERE p.project_id = ? AND d.status IN ('keep', 'reject') ORDER BY p.path",
        (project_id,),
    ).fetchall()
    ctx.set_total(len(rows))
    ctx.stage("writing sidecars")
    for r in rows:
        if ctx.cancelled:
            break
        path = Path(r["path"])
        try:
            if path.suffix.lower() not in ingest.RAW_EXTS or path.suffix.lower() == ".dng":
                ctx.fail(str(path), "JPEG/DNG keeps metadata inside the file; use copy export")
            elif not path.exists():
                ctx.fail(str(path), "original file missing")
            else:
                sidecar = path.with_suffix(".xmp")
                if sidecar.exists() and CREATOR_MARK not in sidecar.read_text(encoding="utf-8", errors="replace"):
                    ctx.fail(str(sidecar), "existing sidecar not written by MythiCull")
                else:
                    sidecar.write_text(xmp_text(r["status"], r["stars"]), encoding="utf-8")
        except OSError as e:
            ctx.fail(str(path), str(e))
        ctx.advance()


MANIFEST = "mythicull_manifest.json"


def _free_names(folder: Path, names: list[str]) -> list[str]:
    """Names with the smallest shared `_n` suffix that leaves every target free (a RAW+JPEG pair stays together)."""
    n = 0
    while True:
        tag = f"_{n}" if n else ""
        out = [Path(x).stem + tag + Path(x).suffix for x in names]
        if not any((folder / o).exists() for o in out):
            return out
        n += 1


def export_copy(ctx: jobs.JobContext, project_id: str, dest: Path, per_chapter: bool) -> None:
    """Job body: copy kept photos and companions into dest, never overwriting; write the manifest."""
    project = ctx.conn.execute("SELECT name FROM projects WHERE id = ?", (project_id,)).fetchone()
    rows = ctx.conn.execute(
        "SELECT p.path, p.companion_path, d.stars, c.position AS pos, COALESCE(c.user_title, c.auto_title) AS title"
        " FROM photos p JOIN decisions d ON d.photo_id = p.id LEFT JOIN chapters c ON c.id = p.chapter_id"
        " WHERE p.project_id = ? AND d.status = 'keep'"
        f" ORDER BY c.position IS NULL, c.position, {db.ADJUSTED_TIME}, p.path",
        (project_id,),
    ).fetchall()
    ctx.set_total(len(rows))
    ctx.stage("copying files")
    chapters: list[dict] = []
    for r in rows:
        if ctx.cancelled:
            break
        src = Path(r["path"])
        try:
            if not src.exists():
                ctx.fail(str(src), "original file missing")
                continue
            folder = dest
            if per_chapter and r["pos"] is not None:
                title = re.sub(r'[\\/:*?"<>|]', "", r["title"] or "").strip()
                folder = dest / f"{r['pos'] + 1:02d} {title}".strip()
            folder.mkdir(parents=True, exist_ok=True)
            comp = Path(r["companion_path"]) if r["companion_path"] else None
            if comp is not None and not comp.exists():
                ctx.fail(str(comp), "companion file missing")
                comp = None
            srcs = [src] + ([comp] if comp else [])
            names = _free_names(folder, [s.name for s in srcs])
            for s, n in zip(srcs, names):
                shutil.copy2(s, folder / n)
            key = str(folder.relative_to(dest)) if folder != dest else ""
            if not chapters or chapters[-1]["folder"] != key or chapters[-1]["_pos"] != r["pos"]:
                chapters.append({"title": r["title"], "folder": key, "_pos": r["pos"], "photos": []})
            chapters[-1]["photos"].append(
                {"filename": names[0], "companion": names[1] if comp else None, "stars": r["stars"]}
            )
        except OSError as e:
            ctx.fail(str(src), str(e))
        ctx.advance()
    for c in chapters:
        del c["_pos"]
    manifest = {
        "project": project["name"] if project else project_id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "chapters": chapters,
    }
    name = _free_names(dest, [MANIFEST])[0]
    (dest / name).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
