# MythiCull: Progress Log

Claude Code updates this file after every task. Keep it short: replace stale entries instead of appending forever.

## Current state
- Next task: **M2.3 Thumbnails and previews**
- Last completed: M2.2 Metadata
- Blockers: none

## Tuned values and model facts
| Item | Value | Source or how it was checked |
| --- | --- | --- |
| Model id | `google/embeddinggemma-2` | |
| Load dtype and device | float32 on CPU | M0.2, Colab session with no GPU (needs transformers from latest release) |
| Seconds per image | 32.4 (CPU, Colab) | M0.2, 117 CC-licensed wedding images from Wikimedia Commons. GPU speed not measured |
| Search query prompt | `task: search result \| query: ` | UNVERIFIED placeholder, not checked against the model card; confirm before M6.1 |
| `chapter_gap_minutes` | 15 (default) | |
| `dup_threshold` | 0.92 (default, untuned) | |
| XMP tested in | TBD (M7.3) | |

## Decisions
- 2026-10-16: spike ran on Colab, not locally (dev machine has 4 GB RAM). Images are CC-licensed Commons photos, not committed.
- 2026-10-16: `config.data_dir()`/`batch_size()` read env per call (tests set env). `db.connect()` migrates on open; `photos` has UNIQUE(project_id, path) for re-import. `camera_offsets` created now though S3-only.
- 2026-10-16: jobs run one daemon thread each with their own DB connection (no queue). Statuses: queued, running, done, failed, cancelled, interrupted. Startup marks leftover queued/running jobs `interrupted`. `failures` is a JSON list of `{item, error}`; a raised exception adds `{item: null, error}` and sets `failed`. Cancel is a DB flag the job polls via `ctx.cancelled`. Routes live under `/api`; `main.py` has only the jobs routes until M1.3.
- 2026-10-16: health route is `/api/health` (per PLAN; SPEC says `/health` under `/api` prefix, same thing). Static `web/` mounted at `/` last in `main.py`; add new routes above it.
- 2026-10-16: `ingest.scan_folder(root)` returns `ScanResult(items, skipped)`; item `path` is RAW when paired. Readability checked by reading 1 byte. Dotfiles are not special-cased (unsupported ext, or ok if named .jpg).
- 2026-10-16: `ingest.read_metadata(path, companion)` returns `PhotoMeta`. `capture_time` is naive local ISO with ms (sorts as text); `time_source` is `exif` (DateTimeOriginal), `exif_modified` (Image DateTime) or `mtime`. M3.2 badge should warn on `mtime` only. RAW falls back to its JPEG companion for tags. Sub-second digits are a decimal fraction ("9" = .9 s). Parsing uses exifread; RAW dimensions via rawpy (untested on real RAW).
<!-- One line each: date, decision, reason. -->

## Dependencies added
fastapi, uvicorn, pydantic, sentence-transformers, torch, rawpy, Pillow, exifread, opencv-python-headless, numpy: stack per AGENTS.md. httpx: FastAPI TestClient. pytest: tests.

## Known issues
- M0.2: query prompt not verified against the model card. 32 s/image on CPU is too slow for a real shoot: re-time on GPU and check batch size and input resolution before M4.2. No NaNs. Top-3 for all three test queries were from the matching category folder.
- M1.2: no per-project job lock. M4.2 must refuse a second index job on a project that already has one active.
- TestClient warns `httpx` with starlette is deprecated (upstream, harmless).
<!-- Open problems to fix before the demo. -->

## Demo numbers (M8.1)
- Photos in:
- Chapters:
- Duplicate groups:
- Photos kept:
- Index time:
- Review time:
