"""Spike: embed up to 20 photos with EmbeddingGemma 2, time it, check NaN, show top 3 per query.

Usage: python scripts/model_spike.py <photo-folder> [--query-prompt "..."]
Read-only on the photo folder.
"""
import argparse
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps
from sentence_transformers import SentenceTransformer

MODEL_ID = "google/embeddinggemma-2"
# TODO(M0.2): replace with the exact text task prompt from the model card, then record it in docs/PROGRESS.md.
QUERY_PROMPT = "task: search result | query: "
QUERIES = ["people dancing", "a group photo", "a speech at a microphone"]
EXTS = {".jpg", ".jpeg", ".png"}


def pick_device() -> tuple[str, torch.dtype]:
    if torch.cuda.is_available():
        return "cuda", torch.bfloat16
    if torch.backends.mps.is_available():
        return "mps", torch.bfloat16
    return "cpu", torch.float32  # never float16


def load(device: str, dtype: torch.dtype) -> tuple[SentenceTransformer, torch.dtype]:
    try:
        return SentenceTransformer(MODEL_ID, device=device, model_kwargs={"torch_dtype": dtype}), dtype
    except Exception as e:  # bfloat16 unsupported -> float32
        if dtype == torch.float32:
            raise
        print(f"bfloat16 failed ({e}); falling back to float32")
        return SentenceTransformer(MODEL_ID, device=device, model_kwargs={"torch_dtype": torch.float32}), torch.float32


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--query-prompt", default=QUERY_PROMPT)
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()

    files = sorted(p for p in args.folder.rglob("*") if p.suffix.lower() in EXTS)[: args.limit]
    if not files:
        raise SystemExit("no JPEG/PNG files found")

    device, dtype = pick_device()
    model, dtype = load(device, dtype)
    print(f"device={device} dtype={dtype} model={MODEL_ID}")

    imgs = [ImageOps.exif_transpose(Image.open(p)).convert("RGB") for p in files]
    t = time.perf_counter()
    emb = model.encode(imgs, batch_size=8, normalize_embeddings=True, convert_to_numpy=True)
    per = (time.perf_counter() - t) / len(files)
    emb = np.asarray(emb, dtype=np.float32)
    print(f"{len(files)} images, {per:.2f} s/image, NaN present: {bool(np.isnan(emb).any())}")

    print(f"query prompt: {args.query_prompt!r}")
    for q in QUERIES:
        qv = model.encode([args.query_prompt + q], normalize_embeddings=True, convert_to_numpy=True)[0]
        top = np.argsort(-(emb @ qv))[:3]
        print(f"\n{q!r}")
        for i in top:
            print(f"  {float(emb[i] @ qv):.3f}  {files[i]}")


if __name__ == "__main__":
    main()
