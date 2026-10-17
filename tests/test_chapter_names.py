import numpy as np
import pytest

from mythicull import db, embed
from tests.conftest import FakeEmbedder
from tests.test_import import client, run_import, wait  # noqa: F401


class CountingEmbedder(FakeEmbedder):
    text_calls = 0

    def encode_text(self, texts):
        self.text_calls += 1
        return super().encode_text(texts)


@pytest.fixture
def indexed(client, photo_folder, monkeypatch):
    """Two chapters of three photos, imported and indexed with a counting fake embedder."""
    fake = CountingEmbedder()
    monkeypatch.setattr(embed, "_embedder", fake)
    pid, job = run_import(client, photo_folder)
    assert wait(client, job)["status"] == "done"
    yield pid, fake
    monkeypatch.setattr(embed, "_embedder", None)


def _index(client, pid):
    assert wait(client, client.post(f"/api/projects/{pid}/index").json()["job_id"])["status"] == "done"


def _suggestions(client, pid):
    return [c["suggested_title"] for c in client.get(f"/api/projects/{pid}/chapters").json()]


def test_no_suggestion_before_indexing_and_model_not_used(client, indexed):
    pid, fake = indexed
    assert _suggestions(client, pid) == [None, None]
    assert fake.text_calls == 0


def test_suggestion_is_best_label_per_chapter(client, indexed):
    pid, fake = indexed
    _index(client, pid)
    ids = [r["id"] for r in db.connect().execute("SELECT id FROM photos WHERE project_id = ? ORDER BY capture_time", (pid,))]
    assert embed.load_store(pid, fake.model_id)[0] == ids  # store is in capture order, so rows 0-2 are chapter 1
    target = fake.encode_text(["ceremony"])[0], fake.encode_text(["first dance"])[0]
    rows = np.stack([target[0]] * 3 + [target[1]] * 3)
    d = embed.project_dir(pid)
    np.save(d / "embeddings.npy", rows)  # same ids file, so the store now holds the planted vectors
    assert _suggestions(client, pid) == ["Ceremony", "First dance"]


def test_label_vectors_encoded_once_across_index_runs(client, indexed):
    pid, fake = indexed
    _index(client, pid)
    calls = fake.text_calls
    assert calls == 1
    _index(client, pid)
    assert fake.text_calls == calls


def test_accepting_sets_user_title_and_keeps_suggestion_available(client, indexed):
    pid, _ = indexed
    _index(client, pid)
    ch = client.get(f"/api/projects/{pid}/chapters").json()[0]
    assert ch["suggested_title"]
    r = client.patch(f"/api/chapters/{ch['id']}", json={"user_title": ch["suggested_title"]}).json()
    assert r["title"] == ch["suggested_title"] and r["user_title"] == ch["suggested_title"]
