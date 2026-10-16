from pathlib import Path

from mythicull import ingest, jobs

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
