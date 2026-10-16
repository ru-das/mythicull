# MythiCull: Progress Log

Claude Code updates this file after every task. Keep it short: replace stale entries instead of appending forever.

## Current state
- Next task: **M4.2c Real index** (manual: you run it)
- Last completed: M4.2b Indexing UI (headless Chromium + fake embedder: bar goes running to done 8/8, no JS errors)
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
- 2026-10-16: `ingest.make_previews(path, companion, out_dir, photo_id, orientation)` writes `<id>_thumb.jpg` (320) and `<id>_preview.jpg` (1600), q85, never upscales, skips if both exist (source not touched). RAW uses the larger of embedded preview and JPEG companion. Orientation: EXIF in the preview wins, else the original's orientation. Raises `PreviewError` when no preview; M2.4 must record it as skip reason/`import_error`. RAW path tested with mocks only, not real RAWs.
- 2026-10-16: `POST /api/projects` {name, folder} -> {project, job_id}; 400 on blank name or missing folder. `ingest.import_project(ctx, project_id)` is the job body: only paths not already in `photos` are added, so existing rows, decisions and cached images are untouched. Migration 2 adds `projects.last_import` (JSON summary: found, imported, already_present, skipped[{path, reason}]), returned by project routes with `photo_count`. Unsupported/unreadable/no-preview files are skipped (not inserted) and also appear in job `failures`. Job `total` = supported photos found. Re-import has no endpoint yet (POST /projects always makes a new project); M3.1 may need one. Images live in `<data_dir>/projects/<id>/images/`.
- 2026-10-16: UI is hash-routed (`#/` list, `#/p/<id>` project, `#/p/<id>/<job_id>` project with live import progress, polls `/api/jobs/<id>` every 500 ms). Reopening a project mid-import shows no progress (no job lookup by project yet) and no re-import button. Not browser-tested here: no playwright in the dev container.
- 2026-10-16: `GET /api/projects/{id}/photos` returns all photos by capture_time (no chapter/view/filter params yet: added in M4.1/M4.3/M5.2). `GET /api/photos/{id}/thumb|preview` serve cached JPEGs with immutable cache headers. Grid uses native `loading=lazy` on `<img>`. Keys: Enter opens first photo, arrows move, Esc/Enter/Space close. Amber `!` badge when `time_source == mtime`.
- 2026-10-16: chapters (`grouping.py`): gap strictly > `chapter_gap_minutes` splits; chapters under 3 photos merge into the nearer neighbour in time (tie: earlier), repeated until none are small. `regenerate_chapters` runs at the end of every import job and synchronously in `PATCH /api/projects/{id}` (timestamps only, fast). It deletes and recreates chapter rows, so chapter ids change on each regenerate. User titles carry to the new chapter with the largest photo overlap (each title and chapter used once; ties go to the first found). Blank rename reverts to the auto title. `GET /photos?chapter=<id>` filters. Sidebar shows title and photo count; kept count waits for M5.
- 2026-10-16: indexing (`embed.py`): store is `<project>/embeddings.npy` + `embedding_ids.json` `{model_id, ids}`, rewritten whole per batch via tmp + `os.replace`, npy first then ids; load trusts ids and slices extra npy rows. Store from another model id counts as empty. Resume = skip ids in store (store is source of truth; `embedded=1` re-synced on start). Sharpness cached in `photos.sharpness`, computed only when NULL. Bad preview or NaN row -> `ctx.fail`, job continues. `POST /projects/{id}/index` -> `{job_id}`, 409 if an index job is active. Model singleton via `embed.get_embedder()`; tests set `embed._embedder`.
- 2026-10-16: UI index control (`web/app.js`): "Index photos" button above the grid, progress bar with cancel, shows last failure text if the job fails (e.g. model download blocked). Reopening a project mid-index shows no progress (no job lookup by project); button then gets a 409 message.
<!-- One line each: date, decision, reason. -->

## Dependencies added
fastapi, uvicorn, pydantic, sentence-transformers, torch, rawpy, Pillow, exifread, opencv-python-headless, numpy: stack per AGENTS.md. httpx: FastAPI TestClient. pytest: tests.

## Known issues
- M0.2: query prompt not verified against the model card. 32 s/image on CPU is too slow for a real shoot: re-time on GPU and check batch size and input resolution before M4.2. No NaNs. Top-3 for all three test queries were from the matching category folder.
- M1.2: index jobs are locked per project (409); import has no lock and index is not blocked while import runs.
- M3.2: checked in headless Chromium (cloud container) with 400 synthetic 3000x2000 JPEGs: import 49 s, 400 cells, 216 thumbs loaded after scrolling (lazy works), preview and arrow keys work, no JS errors. A real shoot has not been scrolled. Photo list is one unpaginated JSON array (fine to ~3000).
- TestClient warns `httpx` with starlette is deprecated (upstream, harmless).
<!-- Open problems to fix before the demo. -->

## Demo numbers (M8.1)
- Photos in:
- Chapters:
- Duplicate groups:
- Photos kept:
- Index time:
- Review time:
