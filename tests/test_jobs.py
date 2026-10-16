import threading
import time

import pytest
from fastapi.testclient import TestClient

from mythicull import db, jobs
from mythicull.main import app


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("MYTHICULL_DATA_DIR", str(tmp_path))
    with TestClient(app) as c:
        yield c


def wait_for(client, job_id, statuses=("done", "failed", "cancelled"), timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in statuses:
            return job
        time.sleep(0.01)
    raise AssertionError(f"job stuck: {job}")


def test_progress(client):
    halfway, resume = threading.Event(), threading.Event()

    def work(ctx):
        ctx.stage("scan")
        ctx.set_total(3)
        ctx.advance()
        halfway.set()
        resume.wait(5)
        ctx.advance(2)

    job_id = jobs.start("test", work)
    assert halfway.wait(5)
    mid = client.get(f"/api/jobs/{job_id}").json()
    assert (mid["status"], mid["stage"], mid["done"], mid["total"]) == ("running", "scan", 1, 3)
    resume.set()
    job = wait_for(client, job_id)
    assert (job["status"], job["done"], job["total"]) == ("done", 3, 3)


def test_cancel(client):
    started = threading.Event()

    def work(ctx):
        ctx.set_total(1000)
        for _ in range(1000):
            if ctx.cancelled:
                return
            ctx.advance()
            started.set()
            time.sleep(0.005)

    job_id = jobs.start("test", work)
    assert started.wait(5)
    assert client.post(f"/api/jobs/{job_id}/cancel").json()["cancel_requested"] is True
    job = wait_for(client, job_id)
    assert job["status"] == "cancelled"
    assert job["done"] < 1000


def test_failures_recorded_and_crash_contained(client):
    def partial(ctx):
        ctx.fail("x.jpg", "bad")
        ctx.advance()

    def crash(ctx):
        raise RuntimeError("boom")

    job = wait_for(client, jobs.start("test", partial))
    assert job["status"] == "done"
    assert job["failures"] == [{"item": "x.jpg", "error": "bad"}]

    job = wait_for(client, jobs.start("test", crash))
    assert job["status"] == "failed"
    assert "boom" in job["failures"][0]["error"]

    assert wait_for(client, jobs.start("test", lambda ctx: None))["status"] == "done"


def test_unknown_job_404(client):
    assert client.get("/api/jobs/nope").status_code == 404
    assert client.post("/api/jobs/nope/cancel").status_code == 404


def test_cancel_finished_job_is_noop(client):
    job = wait_for(client, jobs.start("test", lambda ctx: None))
    after = client.post(f"/api/jobs/{job['id']}/cancel").json()
    assert (after["status"], after["cancel_requested"]) == ("done", False)


def test_mark_interrupted(client):
    conn = db.connect()
    with conn:
        conn.execute(
            "INSERT INTO jobs (id, kind, status, created_at, updated_at) VALUES ('j1', 'test', 'running', 'x', 'x')"
        )
    jobs.mark_interrupted(conn)
    assert jobs.get(conn, "j1")["status"] == "interrupted"
