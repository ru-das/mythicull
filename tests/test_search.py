import numpy as np
import pytest

from mythicull import db, embed
from tests.conftest import FakeEmbedder
from tests.test_import import client, wait  # noqa: F401
from tests.test_index import _use, project  # noqa: F401


class QueryFake(FakeEmbedder):
    """Query vector = mix of stored photo vectors, so the expected ranking is known."""

    def __init__(self, pid, weights):
        super().__init__()
        self.pid, self.weights = pid, weights  # weights: {photo_id: weight}

    def encode_text(self, texts):
        ids, m = embed.load_store(self.pid, self.model_id)
        v = sum(w * m[ids.index(i)] for i, w in self.weights.items())
        return np.stack([v / np.linalg.norm(v)])


def _indexed(client, project, monkeypatch):  # noqa: F811
    _use(monkeypatch, FakeEmbedder())
    assert wait(client, client.post(f"/api/projects/{project}/index").json()["job_id"])["status"] == "done"
    return embed.load_store(project, FakeEmbedder.model_id)[0]


def test_ranking_order_k_and_chapter(client, project, monkeypatch):  # noqa: F811
    ids = _indexed(client, project, monkeypatch)
    a, b, c = ids[4], ids[1], ids[2]
    _use(monkeypatch, QueryFake(project, {a: 1.0, b: 0.6, c: 0.3}))
    got = [p["id"] for p in client.get(f"/api/projects/{project}/search", params={"q": "x"}).json()]
    assert got[:3] == [a, b, c] and len(got) == 6
    assert [p["id"] for p in client.get(f"/api/projects/{project}/search", params={"q": "x", "k": 2}).json()] == [a, b]
    chapter = client.get(f"/api/projects/{project}/chapters").json()[0]["id"]
    assert len(client.get(f"/api/projects/{project}/search", params={"q": "x", "chapter": chapter}).json()) == 6
    assert client.get(f"/api/projects/{project}/search", params={"q": "x", "chapter": "nope"}).json() == []


def test_search_errors_and_unindexed(client, project, monkeypatch):  # noqa: F811
    _use(monkeypatch, FakeEmbedder())
    assert client.get(f"/api/projects/{project}/search", params={"q": "x"}).json() == []  # nothing indexed yet
    assert client.get(f"/api/projects/{project}/search", params={"q": "  "}).status_code == 400
    assert client.get(f"/api/projects/{project}/search", params={"q": "x", "k": 0}).status_code == 422
    assert client.get("/api/projects/nope/search", params={"q": "x"}).status_code == 404


def test_search_model_unavailable(client, project, monkeypatch):  # noqa: F811
    ids = _indexed(client, project, monkeypatch)
    assert ids

    class Broken(FakeEmbedder):
        def encode_text(self, texts):
            raise OSError("offline")

    _use(monkeypatch, Broken())
    r = client.get(f"/api/projects/{project}/search", params={"q": "x"})
    assert r.status_code == 503 and "offline" in r.json()["detail"]


def test_model_load_failure_message(monkeypatch):
    from mythicull import embed

    e = embed.GemmaEmbedder()
    monkeypatch.setattr(e, "_load", lambda: (_ for _ in ()).throw(OSError("offline")))
    with pytest.raises(RuntimeError, match="needs internet"):
        e.encode_text(["x"])
