from fastapi.testclient import TestClient

from mythicull.main import app


def test_health_and_static_shell(tmp_path, monkeypatch):
    monkeypatch.setenv("MYTHICULL_DATA_DIR", str(tmp_path))
    with TestClient(app) as c:
        assert c.get("/api/health").json() == {"status": "ok"}
        r = c.get("/")
        assert r.status_code == 200 and "MythiCull" in r.text
        assert c.get("/api/jobs/nope").status_code == 404


def test_model_status_follows_marker(tmp_path, monkeypatch):
    from mythicull import config

    monkeypatch.setenv("MYTHICULL_DATA_DIR", str(tmp_path))
    with TestClient(app) as c:
        assert c.get("/api/model").json()["ready"] is False
        config.model_dir().mkdir(parents=True)
        (config.model_dir() / ".complete").write_text("ok")
        assert c.get("/api/model").json() == {"ready": True, "path": str(config.model_dir()), "job_id": None}


def test_model_download_reuses_active_job(tmp_path, monkeypatch) -> None:
    import threading
    from mythicull import embed

    release = threading.Event()
    monkeypatch.setenv("MYTHICULL_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(embed, "download_model", lambda ctx: release.wait(5))
    with TestClient(app) as c:
        try:
            first = c.post("/api/model/download").json()["job_id"]
            assert c.post("/api/model/download").json()["job_id"] == first
            assert c.get("/api/model").json()["job_id"] == first
        finally:
            release.set()
            import time
            for _ in range(100):
                if c.get(f"/api/jobs/{first}").json()["status"] not in ("queued", "running"):
                    break
                time.sleep(0.01)
