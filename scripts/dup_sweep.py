"""M4.3c: sweep dup_threshold on a real shoot. Read-only on the photo folder.

Usage: python scripts/dup_sweep.py <photo-folder> [--out dup_sweep_out]
Embeds JPEGs with the app's own embedder, then for consecutive photos taken <= 10 s apart prints
the cosine similarity, how many groups form at each threshold, and writes a contact sheet of pairs
sorted by similarity so you can see where "same burst" turns into "different shot".
"""
import argparse
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from mythicull import ingest
from mythicull.embed import GemmaEmbedder

WINDOW_S = 10
THRESHOLDS = [0.80, 0.85, 0.88, 0.90, 0.92, 0.94, 0.96, 0.98]
EXTS = {".jpg", ".jpeg"}


def load_small(p: Path) -> Image.Image:
    im = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
    im.thumbnail((1600, 1600))  # same size as app previews
    return im


def groups_at(order: list[int], times: list[datetime], emb: np.ndarray, thr: float) -> int:
    n = 1 if order else 0
    for a, b in zip(order, order[1:]):
        close = (times[b] - times[a]).total_seconds() <= WINDOW_S
        if not (close and float(emb[a] @ emb[b]) >= thr):
            n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--out", type=Path, default=Path("dup_sweep_out"))
    args = ap.parse_args()

    files = sorted(p for p in args.folder.rglob("*") if p.suffix.lower() in EXTS)
    if not files:
        raise SystemExit("no JPEGs found")
    metas = [ingest.read_metadata(p) for p in files]
    if any(m.time_source == "mtime" for m in metas):
        print("WARNING: some photos have no EXIF time (mtime fallback); bursts may be wrong")
    order = sorted(range(len(files)), key=lambda i: metas[i].capture_time)
    times = [datetime.fromisoformat(m.capture_time) for m in metas]

    embedder = GemmaEmbedder()
    chunks = [embedder.encode_images([load_small(files[i]) for i in order[k:k + 8]]) for k in range(0, len(order), 8)]
    rows = np.concatenate(chunks).astype(np.float32)
    assert not np.isnan(rows).any(), "NaN in embeddings"
    rows /= np.linalg.norm(rows, axis=1, keepdims=True)
    emb = np.zeros_like(rows)
    emb[order] = rows  # index by original file index

    pairs = [(float(emb[a] @ emb[b]), a, b) for a, b in zip(order, order[1:])
             if (times[b] - times[a]).total_seconds() <= WINDOW_S]
    print(f"{len(files)} photos, {len(pairs)} consecutive pairs within {WINDOW_S} s")
    sims = np.array([s for s, _, _ in pairs])
    if len(sims):
        print("pair similarity percentiles 5/25/50/75/95:", np.round(np.percentile(sims, [5, 25, 50, 75, 95]), 3))
    print("\nthreshold -> groups (fewer groups = more merging)")
    for t in THRESHOLDS:
        print(f"  {t:.2f} -> {groups_at(order, times, emb, t)}")

    args.out.mkdir(exist_ok=True)
    pairs.sort(key=lambda x: x[0])
    step = max(1, len(pairs) // 24)  # about 24 pairs spread over the whole range
    picked = pairs[::step][:24]
    tw = 320
    sheet = Image.new("RGB", (2 * tw * 2 + 30, ((len(picked) + 1) // 2) * (tw + 30)), "white")
    d = ImageDraw.Draw(sheet)
    for k, (s, a, b) in enumerate(picked):
        x, y = (k % 2) * (2 * tw + 30), (k // 2) * (tw + 30)
        d.text((x + 4, y + 4), f"sim {s:.3f}  {(times[b] - times[a]).total_seconds():.1f}s", fill="black")
        for j, i in enumerate((a, b)):
            im = load_small(files[i]); im.thumbnail((tw, tw - 20))
            sheet.paste(im, (x + j * tw, y + 22))
    sheet.save(args.out / "pairs_by_similarity.jpg", quality=85)
    with open(args.out / "pairs.csv", "w") as f:
        f.write("sim,seconds,a,b\n")
        for s, a, b in pairs:
            f.write(f"{s:.4f},{(times[b] - times[a]).total_seconds():.1f},{files[a].name},{files[b].name}\n")
    print(f"\nwrote {args.out}/pairs_by_similarity.jpg and pairs.csv (lowest similarity first)")


if __name__ == "__main__":
    main()
