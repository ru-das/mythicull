import numpy as np
import pytest

from mythicull import embed
from tests.conftest import FakeEmbedder
from tests.test_groups import burst, _groups  # noqa: F401
from tests.test_import import client  # noqa: F401


class VibeEmbedder(FakeEmbedder):
    """Text vector points along axis 1, so burst frames with a larger axis-1 value (later ones) match best."""

    def encode_text(self, texts):
        v = np.zeros((len(texts), 768), dtype=np.float32)
        v[:, 1] = 1
        return v


class BrokenTextEmbedder(FakeEmbedder):
    def encode_text(self, texts):
        raise RuntimeError("no model")


def _pick(client, pid):
    big = next(g for g in _groups(client, pid) if len(g) == 10)
    return [p["id"] for p in big if p["is_group_pick"]]


def _patch(client, pid, **body):
    return client.patch(f"/api/projects/{pid}", json=body)


def test_default_weight(client, burst):
    pid, _ = burst
    assert client.get(f"/api/projects/{pid}").json()["vibe_weight"] == 0.5


def test_weight_moves_pick_and_clearing_restores(client, burst, monkeypatch):
    pid, ids = burst
    monkeypatch.setattr(embed, "_embedder", VibeEmbedder())
    assert _patch(client, pid, dup_threshold=0.92).status_code == 200
    assert _pick(client, pid) == [ids[6]]
    r = _patch(client, pid, vibe_prompt="candid laughter", vibe_weight=1)
    assert r.status_code == 200 and r.json()["vibe_prompt"] == "candid laughter"
    assert _pick(client, pid) == [ids[9]]
    _patch(client, pid, vibe_weight=0)
    assert _pick(client, pid) == [ids[6]]
    _patch(client, pid, vibe_weight=1)
    assert _pick(client, pid) == [ids[9]]
    assert _patch(client, pid, vibe_prompt=None).json()["vibe_prompt"] is None
    assert _pick(client, pid) == [ids[6]]


def test_failed_encode_saves_nothing(client, burst, monkeypatch):
    pid, _ = burst
    monkeypatch.setattr(embed, "_embedder", BrokenTextEmbedder())
    assert _patch(client, pid, vibe_prompt="laughter").status_code == 503
    assert client.get(f"/api/projects/{pid}").json()["vibe_prompt"] is None


def test_regroup_uses_cache_without_model(client, burst, monkeypatch):
    pid, ids = burst
    monkeypatch.setattr(embed, "_embedder", VibeEmbedder())
    _patch(client, pid, vibe_prompt="laughter", vibe_weight=1)
    monkeypatch.setattr(embed, "_embedder", BrokenTextEmbedder())
    assert _patch(client, pid, dup_threshold=0.92).status_code == 200
    assert _pick(client, pid) == [ids[9]]
