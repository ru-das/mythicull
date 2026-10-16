import sqlite3
from pathlib import Path

from mythicull import config

# Append-only: entry N is migration N. Never edit a shipped migration.
MIGRATIONS: list[str] = [
    f"""
    CREATE TABLE projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        folder TEXT NOT NULL,
        created_at TEXT NOT NULL,
        chapter_gap_minutes INTEGER NOT NULL DEFAULT {config.DEFAULT_CHAPTER_GAP_MINUTES},
        dup_threshold REAL NOT NULL DEFAULT {config.DEFAULT_DUP_THRESHOLD},
        vibe_prompt TEXT
    );
    CREATE TABLE chapters (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL REFERENCES projects(id),
        position INTEGER NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        auto_title TEXT NOT NULL,
        user_title TEXT
    );
    CREATE TABLE photos (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL REFERENCES projects(id),
        path TEXT NOT NULL,
        companion_path TEXT,
        filename TEXT NOT NULL,
        file_size INTEGER,
        mtime REAL,
        camera_make TEXT,
        camera_model TEXT,
        capture_time TEXT,
        time_source TEXT,
        width INTEGER,
        height INTEGER,
        orientation INTEGER,
        thumb_path TEXT,
        preview_path TEXT,
        sharpness REAL,
        embedded INTEGER NOT NULL DEFAULT 0,
        chapter_id TEXT REFERENCES chapters(id),
        group_id TEXT,
        is_group_pick INTEGER NOT NULL DEFAULT 0,
        import_error TEXT,
        UNIQUE (project_id, path)
    );
    CREATE INDEX idx_photos_project_time ON photos(project_id, capture_time);
    CREATE INDEX idx_photos_chapter ON photos(chapter_id);
    CREATE TABLE decisions (
        photo_id TEXT PRIMARY KEY REFERENCES photos(id),
        status TEXT CHECK (status IN ('keep', 'reject')),
        stars INTEGER NOT NULL DEFAULT 0 CHECK (stars BETWEEN 0 AND 5),
        updated_at TEXT NOT NULL
    );
    CREATE TABLE jobs (
        id TEXT PRIMARY KEY,
        project_id TEXT REFERENCES projects(id),
        kind TEXT NOT NULL,
        status TEXT NOT NULL,
        stage TEXT,
        done INTEGER NOT NULL DEFAULT 0,
        total INTEGER NOT NULL DEFAULT 0,
        failures TEXT NOT NULL DEFAULT '[]',
        cancel_requested INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE camera_offsets (
        project_id TEXT NOT NULL REFERENCES projects(id),
        camera_model TEXT NOT NULL,
        offset_seconds INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (project_id, camera_model)
    );
    """,
]


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Open the database (creating and migrating it if needed) in WAL mode."""
    path = path or config.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    current = row[0] or 0
    for version in range(current + 1, len(MIGRATIONS) + 1):
        # executescript commits first, so apply each migration plus its version row in one script.
        conn.executescript(f"BEGIN;{MIGRATIONS[version - 1]}INSERT INTO schema_version VALUES ({version});COMMIT;")
