import json
import sqlite3
import threading
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from mythicull import db

ACTIVE = ("queued", "running")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobContext:
    """Handed to a job function to report progress. Owns the job thread's connection."""

    def __init__(self, conn: sqlite3.Connection, job_id: str) -> None:
        self.conn = conn
        self.job_id = job_id

    def _update(self, sql: str, *params: Any) -> None:
        with self.conn:
            self.conn.execute(f"UPDATE jobs SET {sql}, updated_at = ? WHERE id = ?", (*params, _now(), self.job_id))

    def set_total(self, total: int) -> None:
        self._update("total = ?", total)

    def stage(self, name: str) -> None:
        self._update("stage = ?", name)

    def advance(self, n: int = 1) -> None:
        self._update("done = done + ?", n)

    def fail(self, item: str | None, error: str) -> None:
        """Record a per-item failure; the job keeps going."""
        with self.conn:
            row = self.conn.execute("SELECT failures FROM jobs WHERE id = ?", (self.job_id,)).fetchone()
            failures = json.loads(row["failures"]) + [{"item": item, "error": error}]
            self.conn.execute(
                "UPDATE jobs SET failures = ?, updated_at = ? WHERE id = ?", (json.dumps(failures), _now(), self.job_id)
            )

    @property
    def cancelled(self) -> bool:
        row = self.conn.execute("SELECT cancel_requested FROM jobs WHERE id = ?", (self.job_id,)).fetchone()
        return bool(row["cancel_requested"])


def start(kind: str, fn: Callable[[JobContext], None], project_id: str | None = None) -> str:
    """Create a job row and run `fn` in a background thread. Returns the job id immediately."""
    job_id = uuid.uuid4().hex
    conn = db.connect()
    with conn:
        now = _now()
        conn.execute(
            "INSERT INTO jobs (id, project_id, kind, status, created_at, updated_at) VALUES (?, ?, ?, 'queued', ?, ?)",
            (job_id, project_id, kind, now, now),
        )
    conn.close()
    threading.Thread(target=_run, args=(job_id, fn), daemon=True).start()
    return job_id


def _run(job_id: str, fn: Callable[[JobContext], None]) -> None:
    conn = db.connect()
    ctx = JobContext(conn, job_id)
    try:
        ctx._update("status = 'running'")
        fn(ctx)
        ctx._update("status = CASE WHEN cancel_requested THEN 'cancelled' ELSE 'done' END")
    except Exception as e:  # a crashing job must never take the server down
        ctx.fail(None, repr(e))
        ctx._update("status = 'failed'")
    finally:
        conn.close()


def get(conn: sqlite3.Connection, job_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        return None
    job = dict(row)
    job["failures"] = json.loads(job["failures"])
    job["cancel_requested"] = bool(job["cancel_requested"])
    return job


def cancel(conn: sqlite3.Connection, job_id: str) -> bool:
    """Ask a queued or running job to stop. The job sees it via `ctx.cancelled`."""
    with conn:
        cur = conn.execute(
            "UPDATE jobs SET cancel_requested = 1, updated_at = ? WHERE id = ? AND status IN (?, ?)",
            (_now(), job_id, *ACTIVE),
        )
    return cur.rowcount > 0


def mark_interrupted(conn: sqlite3.Connection) -> None:
    """On startup: jobs left active by a killed process will never finish."""
    with conn:
        conn.execute("UPDATE jobs SET status = 'interrupted', updated_at = ? WHERE status IN (?, ?)", (_now(), *ACTIVE))
