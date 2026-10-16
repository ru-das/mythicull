"""M8.1: print the "Demo numbers" block for a project. Read-only; uses the app's own database.

Usage: python scripts/demo_numbers.py <project_id>   (set MYTHICULL_DATA_DIR if not the default)
Review time is not recorded by the app: time your cull yourself.
"""
import sys
from datetime import datetime

from mythicull import db


def numbers(conn, project_id: str) -> dict:
    one = lambda sql: conn.execute(sql, (project_id,)).fetchone()[0]  # noqa: E731
    secs = 0.0
    for r in conn.execute(
        "SELECT created_at, updated_at FROM jobs WHERE project_id = ? AND kind = 'index' AND status = 'done'",
        (project_id,),
    ):
        secs += (datetime.fromisoformat(r["updated_at"]) - datetime.fromisoformat(r["created_at"])).total_seconds()
    return {
        "photos": one("SELECT COUNT(*) FROM photos WHERE project_id = ?"),
        "chapters": one("SELECT COUNT(*) FROM chapters WHERE project_id = ?"),
        "duplicate_groups": one(
            "SELECT COUNT(*) FROM (SELECT group_id FROM photos WHERE project_id = ? AND group_id IS NOT NULL"
            " GROUP BY group_id HAVING COUNT(*) > 1)"
        ),
        "kept": one(
            "SELECT COUNT(*) FROM decisions d JOIN photos p ON p.id = d.photo_id"
            " WHERE p.project_id = ? AND d.status = 'keep'"
        ),
        "index_seconds": secs,  # sum of finished index jobs; a resumed run counts only its own pass
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    n = numbers(db.connect(), sys.argv[1])
    print(f"- Photos in: {n['photos']}")
    print(f"- Chapters: {n['chapters']}")
    print(f"- Duplicate groups: {n['duplicate_groups']}")
    print(f"- Photos kept: {n['kept']}")
    print(f"- Index time: {n['index_seconds'] / 60:.1f} min")
