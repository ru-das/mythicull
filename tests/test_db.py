from mythicull import config, db

TABLES = {"projects", "photos", "chapters", "decisions", "jobs", "camera_offsets", "schema_version"}


def test_fresh_db_has_all_tables_and_version(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert TABLES <= names
    assert conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == 2
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_reconnect_does_not_remigrate(tmp_path):
    db.connect(tmp_path / "t.db").close()
    conn = db.connect(tmp_path / "t.db")
    assert conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0] == 2


def test_config_env(monkeypatch, tmp_path):
    monkeypatch.setenv("MYTHICULL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MYTHICULL_BATCH_SIZE", "3")
    assert config.data_dir() == tmp_path
    assert config.batch_size() == 3
