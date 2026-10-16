# MythiCull: Product Spec

## Who it's for
Wedding and event photographers culling 300 to 3,000 photos per shoot who want to finish faster without uploading client photos anywhere.

## Promise
Point MythiCull at a shoot folder. It groups the shoot into the story of the day, finds moments by plain-English search, suggests the best frame from each burst, and sends your picks to Lightroom. Nothing leaves your laptop.

## Supported files
- JPEG: `.jpg`, `.jpeg`
- RAW, through the embedded preview only: `.cr2`, `.cr3`, `.nef`, `.arw`, `.raf`, `.dng`
- Extensions are matched case-insensitively. Subfolders are scanned recursively.
- RAW+JPEG pairs (same folder, same basename) are one photo: the RAW is the original (`path`), the JPEG is the `companion_path`. Use whichever preview is larger.
- Unsupported or unreadable files are skipped and listed with a reason in the import summary. They never crash the import.

## Core features (must ship)

### F1. Projects
- Create a project from a name and an absolute folder path typed into a text field.
- List and reopen existing projects.
- Acceptance: creating a project on a 300-photo folder shows an import summary (found, imported, skipped with reasons).

### F2. Import
- For each photo store: UUID, absolute path, companion path, filename, file size, mtime, camera make and model, capture time, time source, width, height, orientation.
- Capture time: EXIF `DateTimeOriginal` plus `SubSecTimeOriginal` when present, read with exifread. Fallback 1: the EXIF of the embedded preview. Fallback 2: file mtime, with `time_source = "mtime"` shown as a warning in the UI. Store as a naive local ISO timestamp.
- Generate a grid thumbnail (long edge 320 px) and a preview (long edge 1600 px) as JPEG in the project data folder, with EXIF orientation applied.
- RAW previews come from `rawpy` `extract_thumb()`. Convert bitmap thumbs to JPEG. If a RAW has no usable preview, skip it with a reason.
- Re-importing the same folder adds only new files and leaves existing photos and decisions untouched.
- Import never loads the model.
- Acceptance: a 300-photo import finishes and the grid is browsable before any indexing starts.

### F3. Indexing
- Background job that embeds every preview with EmbeddingGemma 2 and computes sharpness.
- Sharpness: variance of the Laplacian on the grayscale preview downscaled to 1024 px long edge.
- Reports stage, done, total and failures. Can be cancelled. Resumes after a crash or restart, skipping photos already embedded.
- Acceptance: stop the server mid-index, restart it, start indexing again, and it continues from where it stopped.

### F4. Story chapters
- Sort photos by capture time. Start a new chapter whenever the gap to the previous photo exceeds `chapter_gap_minutes` (default 15, per-project setting).
- Merge chapters with fewer than 3 photos into the nearest chapter in time.
- Default title: `Chapter N · 5:02 PM to 5:41 PM`. The user can rename any chapter.
- When chapters are regenerated (for example after changing the gap), a user-renamed title moves to the new chapter with the largest photo overlap.
- Chapters need only timestamps, so they work before indexing.
- Acceptance: a synthetic test with known gaps produces exactly the expected chapters.

### F5. Duplicate groups and suggested picks
- Within a chapter, walk photos in time order. A photo joins the previous photo's group when it was taken at most 10 seconds later and the image-embedding cosine similarity is at least `dup_threshold` (default 0.92, tune on real photos).
- The suggested pick of each group is the photo with the highest sharpness. A photo with no near-duplicates is its own group and pick.
- "Best" view shows one tile per group with a count badge; clicking the badge expands the group. "All" view shows every photo.
- Acceptance: a 10-frame burst collapses into one tile with a "10" badge, and the suggested pick is the sharpest frame.

### F6. Search
- A search box. Embed the query with the model's text prompt, compute cosine similarity against all image embeddings, and return the top 50 (configurable) ranked results. Optionally limit to one chapter.
- Results appear in the grid and can be rated like any other photo.
- Acceptance: on a real shoot, most of the top 10 results for "people dancing" show dancing. Record the check in `docs/PROGRESS.md`.

### F7. Review workspace
- Layout: chapter sidebar on the left (title, time range, photo count, kept count); top bar with search, Best/All toggle, filter (All, Unreviewed, Kept, Rejected) and counters; grid in the centre; large preview overlay.
- Thumbnails lazy-load so 3,000 photos scroll smoothly.
- Keyboard shortcuts (Lightroom-style):
  - Arrow keys: move selection
  - Enter or Space: open or close large preview; Esc: close
  - `P`: keep; `X`: reject; `U`: clear
  - `1` to `5`: set stars; `0`: clear stars
  - `/`: focus search
  - Ctrl+Z or Cmd+Z: undo the last decision
  - Auto-advance to the next photo after `P` or `X` (on by default, toggleable)
- Every decision is saved immediately with one API call and survives a restart.
- Acceptance: cull 100 photos using only the keyboard, restart the server, and every decision is still there.

### F8. Export
- XMP sidecars (RAW files only): write `<basename>.xmp` next to each RAW that has a decision.
  - Keep: `xmp:Rating` = stars (minimum 1), `xmp:Label="Green"`
  - Reject: `xmp:Rating="0"`, `xmp:Label="Red"`
  - Always include `xmp:CreatorTool="MythiCull"`.
  - Follow the existing-sidecar rule in `CLAUDE.md`.
  - JPEG and DNG files are skipped here because Lightroom reads their metadata from inside the file, not from sidecars. The summary tells the user to use copy export for them.
- Copy export: copy kept photos (and their companions) to a chosen destination folder, optionally into one subfolder per chapter. Write `mythicull_manifest.json` listing chapters in order with their filenames and ratings. Follow the copy rules in `CLAUDE.md`.
- Both exports show a summary: written, skipped (with reasons).
- Acceptance: RAW files with MythiCull sidecars show the right stars and colour labels when imported into Lightroom Classic or another app that reads `basename.xmp` sidecars. Record the app and version tested in `docs/PROGRESS.md`.

## Stretch features (only after F1 to F8 pass)
- **S1. Suggested chapter names.** Compare each chapter's mean image embedding against text embeddings of a fixed list of moments: getting ready, details and decor, ceremony, vows, ring exchange, first kiss, family group photos, couple portraits, cocktail hour, reception entrance, speeches, first dance, cake cutting, dance floor, keynote, awards, audience, venue exterior. Show the best label as a suggestion the user can accept or ignore.
- **S2. Vibe prompt.** A per-project text instruction such as "prioritise candid laughter". The suggested pick in each group becomes a blend of sharpness rank and vibe-similarity rank, with a weight slider. Uses existing embeddings only.
- **S3. Per-camera time offset.** List detected camera bodies, let the user set an offset in seconds per body, then regenerate chapters and groups. Never writes to originals.

## Out of scope (do not build without explicit approval)
Face or VIP recognition, PDF event-brief parsing, desktop packaging (Tauri, Electron), full RAW decoding or editing, album or storyboard layouts, cloud models or uploads, user accounts, preference learning, FAISS or any vector database.

## Data model (SQLite)
- `projects`: id, name, folder, created_at, chapter_gap_minutes, dup_threshold, vibe_prompt (nullable)
- `photos`: id (UUID), project_id, path, companion_path, filename, file_size, mtime, camera_make, camera_model, capture_time, time_source, width, height, orientation, thumb_path, preview_path, sharpness, embedded (bool), chapter_id, group_id, is_group_pick, import_error
- `chapters`: id, project_id, position, start_time, end_time, auto_title, user_title (nullable)
- `decisions`: photo_id (primary key), status (`keep`, `reject` or null), stars (0 to 5), updated_at. Analysis code never writes to this table.
- `jobs`: id, project_id, kind, status, stage, done, total, failures (JSON), cancel_requested, created_at, updated_at
- `camera_offsets` (S3 only): project_id, camera_model, offset_seconds
- `schema_version`
- Embeddings, outside SQLite: `<data_dir>/projects/<project_id>/embeddings.npy` (float32, N x 768, L2-normalised) with `embedding_ids.json` (photo ids in row order) and the model id.

## API (JSON, prefix `/api`)
- `GET /health`
- `POST /projects` (name, folder) → project, import job id
- `GET /projects`, `GET /projects/{id}`
- `PATCH /projects/{id}` (chapter_gap_minutes, dup_threshold, vibe_prompt) → regroups
- `POST /projects/{id}/index` → job id
- `GET /jobs/{id}`, `POST /jobs/{id}/cancel`
- `GET /projects/{id}/chapters`, `PATCH /chapters/{id}` (user_title)
- `GET /projects/{id}/photos?chapter=&view=best|all&filter=`
- `GET /photos/{id}/thumb`, `GET /photos/{id}/preview`
- `PUT /photos/{id}/decision` (status, stars)
- `GET /projects/{id}/search?q=&k=&chapter=`
- `POST /projects/{id}/export/xmp`, `POST /projects/{id}/export/copy` (destination, per_chapter)

Adjust endpoints if needed and note changes in `docs/PROGRESS.md`.

## Non-functional requirements
- Works offline after the model download.
- Browsing and rating work before indexing finishes and without the model.
- A crash or kill never corrupts the database (transactions, WAL mode).
- Missing or unsupported files are reported clearly and never crash the app.
