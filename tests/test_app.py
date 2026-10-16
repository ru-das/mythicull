from fastapi.testclient import TestClient

from mythicull.main import app


def test_health_and_static_shell(tmp_path, monkeypatch):
    monkeypatch.setenv("MYTHICULL_DATA_DIR", str(tmp_path))
    with TestClient(app) as c:
        assert c.get("/api/health").json() == {"status": "ok"}
        r = c.get("/")
        assert r.status_code == 200 and "MythiCull" in r.text
        assert c.get("/api/jobs/nope").status_code == 404
