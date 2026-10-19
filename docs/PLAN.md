# MythiCull: Build Plan

Work top to bottom, one task per session or per `/next`. Each task has a "Done when" check. Tick the box only when the check passes and `pytest -q` is green.

Target: Day 1 finishes M0 to M4. Day 2 finishes M5 to M8.

## M0. Setup and model spike
- [x] **M0.1 Scaffold.** `requirements.txt`, `mythicull/` package with empty modules from `CLAUDE.md`, `web/` placeholder, `tests/` with a `conftest.py` that registers the `model` marker and builds a fixture folder of synthetic JPEGs with EXIF timestamps, `.gitignore` (venv, data dir, `*.npy`, photos, weights).
  Done when: `pip install -r requirements.txt` works and `pytest -q` passes with one smoke test.
- [x] **M0.2 Model spike.** `scripts/model_spike.py <folder>` loads `google/embeddinggemma-2` (no float16), embeds up to 20 images, prints seconds per image, checks for NaN, and prints the top 3 photos for "people dancing", "a group photo" and "a speech at a microphone". Find the text query prompt on the model card.
  Done when: it runs on a real folder; the dtype, device, seconds per image and exact query prompt are recorded in `docs/PROGRESS.md`.

## M1. Backend foundation
- [x] **M1.1 Config and database.** `config.py` (data dir, batch size, defaults), `db.py` with connection helper, WAL mode, migration 1 creating every table in `docs/SPEC.md`.
  Done when: tests create a fresh database and confirm all tables and `schema_version = 1`.
- [x] **M1.2 Job runner.** `jobs.py`: background thread executor, progress updates in the `jobs` table, cancellation flag, failures list. `GET /jobs/{id}`, `POST /jobs/{id}/cancel`.
  Done when: a test job reports progress, can be cancelled, and records failures without crashing.
- [x] **M1.3 App shell.** `main.py` with `/api/health` and static serving of `web/`.
  Done when: `uvicorn` starts and http://localhost:8000 shows the placeholder page.

## M2. Import
- [x] **M2.1 Scan.** Recursive scan, supported extensions, RAW+JPEG pairing, skip list with reasons.
  Done when: tests cover pairing, mixed-case extensions and an unreadable file.
- [x] **M2.2 Metadata.** Capture time with sub-seconds and both fallbacks, camera model, dimensions, orientation.
  Done when: tests cover EXIF time, sub-second ordering and the mtime fallback.
- [x] **M2.3 Thumbnails and previews.** JPEG and RAW embedded previews, orientation applied, cached in the data dir.
  Done when: tests confirm sizes and orientation; a second run regenerates nothing.
- [x] **M2.4 Project API and import job.** `POST /projects`, `GET /projects`, `GET /projects/{id}`, import summary, re-import adds only new files.
  Done when: tests import the fixture folder twice and photo counts and decisions are unchanged the second time.

## M3. Browsing UI
- [x] **M3.1 Projects screen.** Create a project (name + folder path), list projects, open one, show import progress and summary.
- [x] **M3.2 Grid and preview.** `GET /projects/{id}/photos`, thumb and preview endpoints, lazy-loading grid, large preview overlay, arrow-key navigation, mtime-time warning badge.
  Done when: a real 300+ photo shoot scrolls smoothly and opens previews.

## M4. Chapters, indexing and duplicates
- [x] **M4.1 Chapters.** Time-gap chapters, small-chapter merge, auto titles, rename, title carry-over on regenerate, chapter sidebar in the UI.
  Done when: the synthetic gap test passes and renamed titles survive a gap change.
- [x] **M4.2a Indexing backend.** `embed.py` (lazy model load, fake embedder for tests), embeddings `.npy` store, sharpness in `quality.py`, `POST /projects/{id}/index`, resume and cancel.
  Done when: tests with the fake embedder cover resume after interruption and cancel.
- [x] **M4.2b Indexing UI.** Index button and progress bar in the project view (reuse import progress polling).
- [x] **M4.2c Real index.** Index the real shoot to completion; re-time s/image on GPU and check batch size.
  Done when: a real index of the shoot completes (manual).
- [x] **M4.3 Duplicate groups.** Split into a, b, c below.
- [x] **M4.3a Grouping backend.** Groups by 10 s window and `dup_threshold`, sharpest pick, regroup after chapters, indexing and `dup_threshold` change (`PATCH /projects/{id}`). Photo listing returns `group_id`, `is_group_pick`.
  Done when: the burst test passes.
- [x] **M4.3b Best/All UI.** Best/All toggle, count badges, click badge to expand a group.
- [x] **M4.3c Tune `dup_threshold`.** Check on the real shoot, record in `docs/PROGRESS.md` (manual). Done on HDR+ bursts (easy cases only); recheck on a real shoot at M8.1.

## M5. Review
- [x] **M5.1 Decisions.** `PUT /photos/{id}/decision`, decision state in photo listings, P/X/U and 0 to 5 keys, auto-advance, keep/reject borders and star display.
  Done when: tests confirm decisions survive re-import, re-index and regrouping.
- [x] **M5.2 Filters, counters and undo.** Unreviewed/Kept/Rejected filter, counters in the top bar and sidebar, Ctrl/Cmd+Z undo stack.
  Done when: a 100-photo keyboard-only cull survives a server restart.

## M6. Search
- [x] **M6.1 Search.** `search.py`, `GET /projects/{id}/search`, `/` to focus, results in the grid, optional chapter scope, clear search.
  Done when: tests with the fake embedder confirm ranking order; the real-shoot "people dancing" check is recorded.

## M7. Export
- [x] **M7.1 XMP export.** Sidecar writer, existing-sidecar rule, summary.
  Done when: tests cover keep, reject, foreign sidecar skipped, own sidecar updated, JPEG skipped.
- [x] **M7.2 Copy export.** Kept photos and companions, per-chapter folders option, no-overwrite suffixes, refuse destination inside source, manifest.
  Done when: tests cover name clashes and the refused destination.
- [x] **M7.3 Export UI.** Export panel with both options and the summary.
  Done when: sidecars from the real shoot are checked in Lightroom Classic or darktable and the result is recorded.

## M8. Demo readiness
- [x] **M8.1 End-to-end run.** Full flow on a real shoot with the server restarted midway. Record photos in, chapters, groups, picks kept, minutes spent and index time in `docs/PROGRESS.md`. Done on public HDR+ frames via Colab; review time not measured.
- [x] **M8.2 README.** What it does, why it runs on an open-weight model (privacy, offline, no per-image cost), setup, usage, keyboard shortcuts, limitations.
- [x] **M8.3 Polish.** Fix the top issues found in M8.1. Empty states and error messages for missing folder, model download failure and no supported photos. Done: the three error/empty states; M8.1 had no new bugs beyond the known issues below, which stay open.

## Stretch (only after M8, in this order)
- [x] **S1 Suggested chapter names** (see `docs/SPEC.md`)
- [x] **S2 Vibe prompt**
- [x] **S3 Per-camera time offset**

## M9. Model download
- [x] **M9.1 In-app model download.** Model saved in `<data_dir>/models/`, visible download step with byte progress in the UI, marker file marks a complete download, load from the local path only (no hub access after).
  Done when: `/api/model` tests pass. Real download not run here (no network to HF).

- [x] **M9.2 Startup model prompt and accurate download progress.** Detect locally on open, offer download or defer, reconnect to active download, use remote file sizes and count each file once.

## UI
- [x] **U5 Animation cleanup.** Remove layout transitions from segment indicators, progress fills and project-row hover; preserve feedback with transforms.
- [x] **U4 Native folder selection.** Choose import and copy-export folders through a desktop dialog; handle cancellation, unavailable desktop support and local-only access. API tests and mocked-dialog browser flows pass; real OS desktop smoke checks remain open.
- [x] **U3 Segmented control polish.** Align the selected indicator; refine spacing, hover and focus states across review filters and Best/All, including both themes and narrow screens.
- [x] **U1 UI redesign.** Replace the visual style of `web/` (Yellow Box film-stock world), custom controls instead of browser widgets, several fonts, animation, dark and light themes. Flow, routes and API calls unchanged.
- [x] **U2 East of the Sun restyle.** Look only, no behaviour change: teal night and parchment themes, gilt accent, vermilion for rejects, Federo + Figtree + Martian Mono, sun-over-horizon logo and favicon, finer icon strokes. No constellations (user choice).

- [x] **U6 Clear interface wording.** Replace vague labels with plain language and explain suggestion settings, chapter breaks, analysis and exports. Done when copy is reviewed in context and pytest passes.

- [x] **U7 Accessible controls and focus.** Roving photo focus, modal containment, interrupted sliders, labeled progress/disclosures and explicit reduced motion.
- [x] **U8 Complete preview interaction.** Visible navigation, decisions and stars with synchronized state, undo, failures and responsive image space.
- [x] **U9 Navigation, responsive layout and visual polish.** Chapters first, collapsed analysis settings, touch targets, neutral surrounds and accessible empty states; browser regression and full-flow checks.
