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


_READY_MARKER = ".complete"


def model_ready() -> bool:
    """True once a full download finished. The marker is written last, so a partial download never counts."""
    return (config.model_dir() / _READY_MARKER).is_file()


def download_model(ctx: jobs.JobContext) -> None:
    """Job body: fetch the model once into the data dir. Progress is in bytes. Resumes after an interruption."""
    from huggingface_hub import HfApi, hf_hub_download
    from tqdm.auto import tqdm

    if model_ready():
        return
    ctx.stage("checking download size")
    info = HfApi().model_info(config.MODEL_ID, files_metadata=True)
    files = info.siblings
    if not files or any(f.size is None for f in files):
        raise RuntimeError("Hugging Face did not provide the model file sizes. Please retry.")
    ctx.set_total(sum(f.size for f in files))
    d = config.model_dir()
    d.mkdir(parents=True, exist_ok=True)
    completed = 0
    reported = 0

    class _Bar(tqdm):
        def update(self, n: float | None = 1) -> bool | None:
            nonlocal reported
            if ctx.cancelled:
                raise InterruptedError("Model download cancelled; retry to resume.")
            result = super().update(n)
            # Count logical file bytes, including resumed bytes, never transfer/retry bytes.
            if self.unit == "B" and "transfer" not in str(self.desc).lower():
                current = completed + min(file.size, int(self.n))
                if current > reported:
                    ctx.advance(current - reported)
                    reported = current
            return result

    ctx.stage("downloading")
    for file in files:
        if ctx.cancelled:
            return
        try:
            hf_hub_download(config.MODEL_ID, filename=file.rfilename, revision=info.sha,
                            local_dir=d, tqdm_class=_Bar)
        except InterruptedError:
            if ctx.cancelled:
                return
            raise
        completed += file.size
        if completed > reported:  # Cached files have no progress bar.
            ctx.advance(completed - reported)
            reported = completed
    if not ctx.cancelled:
        (d / _READY_MARKER).write_text("ok")


class GemmaEmbedder:
    """EmbeddingGemma 2, loaded on first use. float32 on CPU, bfloat16 on GPU, never float16."""

    model_id = config.MODEL_ID

    def __init__(self) -> None:
        self._model = None

    def _load(self):  # noqa: ANN202 - torch/sentence-transformers imported lazily
        import torch
        from sentence_transformers import SentenceTransformer

        if not model_ready():
            raise FileNotFoundError("model not downloaded")
        path = str(config.model_dir())
        if torch.cuda.is_available():
            device, dtype = "cuda", torch.bfloat16
        elif torch.backends.mps.is_available():
            device, dtype = "mps", torch.bfloat16
        else:
            device, dtype = "cpu", torch.float32
        try:
            return SentenceTransformer(path, device=device, model_kwargs={"torch_dtype": dtype})
        except Exception:
            if dtype == torch.float32:
                raise
            return SentenceTransformer(path, device=device, model_kwargs={"torch_dtype": torch.float32})

    def _encode(self, items: list) -> np.ndarray:
        if self._model is None:
            try:
                self._model = self._load()
            except Exception as e:
                raise RuntimeError(
                    f"Could not load model {self.model_id}. Download it first (one time, needs internet) "
                    f"with the model download button. ({e})"
                ) from e
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
    ctx.stage("grouping")
    from mythicull import grouping  # grouping imports embed

    grouping.save_label_vectors(embedder)
    grouping.regroup(conn, project_id)
