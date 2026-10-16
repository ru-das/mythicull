import json
import os
import threading
from pathlib import Path
from typing import Protocol

import numpy as np
from PIL import Image

from mythicull import config, jobs

# Text task prompt for search queries; UNVERIFIED against the model card (see docs/PROGRESS.md).
QUERY_PROMPT = "task: search result | query: "


class Embedder(Protocol):
    model_id: str

    def encode_images(self, images: list[Image.Image]) -> np.ndarray: ...

    def encode_text(self, texts: list[str]) -> np.ndarray: ...


class GemmaEmbedder:
    """EmbeddingGemma 2, loaded on first use. float32 on CPU, bfloat16 on GPU, never float16."""

    model_id = config.MODEL_ID

    def __init__(self) -> None:
        self._model = None

    def _load(self):  # noqa: ANN202 - torch/sentence-transformers imported lazily
        import torch
        from sentence_transformers import SentenceTransformer

        if torch.cuda.is_available():
            device, dtype = "cuda", torch.bfloat16
        elif torch.backends.mps.is_available():
            device, dtype = "mps", torch.bfloat16
        else:
            device, dtype = "cpu", torch.float32
        try:
            return SentenceTransformer(self.model_id, device=device, model_kwargs={"torch_dtype": dtype})
        except Exception:
            if dtype == torch.float32:
                raise
            return SentenceTransformer(self.model_id, device=device, model_kwargs={"torch_dtype": torch.float32})

    def _encode(self, items: list) -> np.ndarray:
        if self._model is None:
            self._model = self._load()
        out = self._model.encode(items, batch_size=config.batch_size(), normalize_embeddings=True, convert_to_numpy=True)
        return np.asarray(out, dtype=np.float32)

    def encode_images(self, images: list[Image.Image]) -> np.ndarray:
        return self._encode(images)

    def encode_text(self, texts: list[str]) -> np.ndarray:
        return self._encode([QUERY_PROMPT + t for t in texts])


_embedder: Embedder | None = None
_lock = threading.Lock()


def get_embedder() -> Embedder:
    """One embedder per process. Tests set `embed._embedder` to a fake."""
    global _embedder
    with _lock:
        if _embedder is None:
            _embedder = GemmaEmbedder()
        return _embedder


def project_dir(project_id: str) -> Path:
    return config.data_dir() / "projects" / project_id


def load_store(project_id: str, model_id: str) -> tuple[list[str], np.ndarray]:
    """Return (photo ids, matrix) for the project. A store from another model counts as empty."""
    d = project_dir(project_id)
    try:
        meta = json.loads((d / "embedding_ids.json").read_text())
        matrix = np.load(d / "embeddings.npy")
    except (FileNotFoundError, ValueError):
        return [], np.zeros((0, 0), dtype=np.float32)
    if meta.get("model_id") != model_id:
        return [], np.zeros((0, 0), dtype=np.float32)
    ids = meta["ids"]
    # The ids file is written last, so a crash can leave extra npy rows: trust the ids.
    return ids, matrix[: len(ids)]


def append_store(project_id: str, model_id: str, ids: list[str], rows: np.ndarray) -> None:
    old_ids, old = load_store(project_id, model_id)
    matrix = rows if not old_ids else np.vstack([old, rows])
    d = project_dir(project_id)
    d.mkdir(parents=True, exist_ok=True)
    # shortcut: rewrites the whole npy per batch, fine to ~10k photos, then append in chunks
    tmp_npy, tmp_ids = d / "embeddings.tmp.npy", d / "embedding_ids.tmp.json"
    np.save(tmp_npy, matrix.astype(np.float32))
    tmp_ids.write_text(json.dumps({"model_id": model_id, "ids": old_ids + ids}))
    os.replace(tmp_npy, d / "embeddings.npy")
    os.replace(tmp_ids, d / "embedding_ids.json")


def index_project(ctx: jobs.JobContext, project_id: str) -> None:
    """Job body: embed every previewed photo not yet in the store, and cache sharpness."""
    from mythicull import quality

    conn = ctx.conn
    embedder = get_embedder()
    rows = conn.execute(
        "SELECT id, preview_path, sharpness FROM photos WHERE project_id = ? AND preview_path IS NOT NULL "
        "ORDER BY capture_time, filename",
        (project_id,),
    ).fetchall()
    ctx.set_total(len(rows))
    stored_ids, _ = load_store(project_id, embedder.model_id)
    stored = set(stored_ids)
    with conn:  # repairs a crash between the store write and the DB update
        conn.executemany("UPDATE photos SET embedded = 1 WHERE id = ?", [(i,) for i in stored])
    todo = [r for r in rows if r["id"] not in stored]
    ctx.advance(len(rows) - len(todo))
    ctx.stage("indexing")
    step = config.batch_size()
    for start in range(0, len(todo), step):
        if ctx.cancelled:
            return
        ids: list[str] = []
        images: list[Image.Image] = []
        sharp: dict[str, float] = {}
        for r in todo[start : start + step]:
            try:
                with Image.open(r["preview_path"]) as im:
                    images.append(im.convert("RGB"))
                if r["sharpness"] is None:
                    sharp[r["id"]] = quality.sharpness(Path(r["preview_path"]))
                ids.append(r["id"])
            except Exception as e:  # one bad preview must not stop the job
                images = images[: len(ids)]
                ctx.fail(r["id"], repr(e))
                ctx.advance()
        if not ids:
            continue
        vecs =embedder.encode_images(images)
        ok = ~np.isnan(vecs).any(axis=1)
        for i, good in zip(ids, ok):
            if not good:
                ctx.fail(i, "NaN embedding")
        good_ids = [i for i, g in zip(ids, ok) if g]
        if good_ids:
            append_store(project_id, embedder.model_id, good_ids, vecs[ok])
        with conn:
            for i in ids:
                if i in sharp:
                    conn.execute("UPDATE photos SET sharpness = ? WHERE id = ?", (sharp[i], i))
            conn.executemany("UPDATE photos SET embedded = 1 WHERE id = ?", [(i,) for i in good_ids])
        ctx.advance(len(ids))
