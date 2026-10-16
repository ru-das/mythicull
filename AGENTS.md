# MythiCull

Local-first photo culling app for wedding and event photographers. It imports a shoot, indexes it with the open-weight EmbeddingGemma 2 model, groups photos into time-based story chapters and near-duplicate bursts, supports plain-English search, and exports picks as XMP sidecars or copied files. It runs fully offline after the one-time model download.

## Project docs (read when relevant, not every turn)
- `docs/PROGRESS.md`: current state, decisions, tuned values, known issues. Read at the start of every session.
- `docs/PLAN.md`: ordered task checklist with task ids (M0.1, M0.2, ...). Work top to bottom.
- `docs/SPEC.md`: features, acceptance criteria, data model, API, out-of-scope list.

## Stack
- Python 3.11+, FastAPI + Uvicorn, Pydantic v2
- sentence-transformers + PyTorch running `google/embeddinggemma-2`
- rawpy (RAW embedded previews), Pillow, exifread, opencv-python-headless, NumPy
- SQLite through the standard `sqlite3` module, no ORM
- Frontend: plain HTML, CSS and vanilla JavaScript (ES modules) in `web/`, served by FastAPI. No Node, no build step.
- Tests: pytest

## Layout
- `mythicull/`: Python package. `main.py` (app and routes), `config.py`, `db.py`, `jobs.py`, `ingest.py`, `embed.py`, `quality.py`, `grouping.py`, `search.py`, `export.py`
- `web/`: `index.html`, `app.js`, `styles.css`
- `tests/`: pytest suite. Fixtures generate small synthetic JPEGs; no real photos in the repo.
- `scripts/`: one-off spikes and benchmarks
- Runtime data lives in `MYTHICULL_DATA_DIR` (default `~/.mythicull`), never inside the repo.

## Commands
- Setup: `python -m venv .venv`, activate it, then `pip install -r requirements.txt`
- Run: `uvicorn mythicull.main:app --reload --port 8000`, then open http://localhost:8000
- Tests: `pytest -q` (fast, never loads the model)
- Model tests: `pytest -q -m model`
- Model spike: `python scripts/model_spike.py <photo-folder>`

## Hard rules
- Photo folders are read-only. Never move, rename, modify or delete an original file. The only files MythiCull may create inside a photo folder are `.xmp` sidecars from XMP export.
- Never overwrite an existing `.xmp` unless it contains `xmp:CreatorTool="MythiCull"`. Otherwise skip it and list it in the export summary.
- Copy export never overwrites a file in the destination (add a numeric suffix instead) and refuses a destination inside the source folder.
- No network calls at runtime except the one-time model download. No telemetry, no cloud APIs.
- Never load the model in float16: it produces NaN or degraded embeddings. Use float32 on CPU and bfloat16 on GPU (fall back to float32 if bfloat16 is unsupported).
- Never recompute cached thumbnails, previews or embeddings. Embeddings are keyed by photo id and model id.
- Re-running import, indexing or grouping must never delete or change user decisions (keep, reject, stars) or user-renamed chapter titles.

## Model notes
- Text-to-image and image-to-image scores are not calibrated against each other. Use text-to-image scores only to rank results within one query; never apply a fixed threshold to them.
- Image-to-image cosine similarity is fine for the duplicate threshold. Tune it on real photos and record the value in `docs/PROGRESS.md`.
- For search queries, use the text task prompt given on the EmbeddingGemma 2 model card. Record the exact prompt in `docs/PROGRESS.md`.
- Load the model lazily on the first index or search request, once per process. Device order: CUDA, then MPS, then CPU. Batch size comes from `MYTHICULL_BATCH_SIZE` (default 8).

## Code conventions
- Type hints on all functions. Pydantic models for every API request and response body.
- Parameterized SQL only. Enable WAL mode. Schema changes go through numbered migrations in `db.py` tracked in a `schema_version` table.
- Long work (import, indexing, export) runs through the job runner in `jobs.py` and reports progress. API handlers return immediately with a job id.
- Unit tests never load the real model: inject a fake embedder that returns deterministic vectors. Mark real-model tests with `@pytest.mark.model`.
- Browsing and rating must work before indexing finishes and when the model is unavailable.
- Add new dependencies to `requirements.txt` and note why in `docs/PROGRESS.md`.
- Never commit photos, model weights, `.npy` files or runtime data.

## Workflow
- Do one `docs/PLAN.md` task at a time. After each task: run `pytest -q`, tick its box in `docs/PLAN.md`, update `docs/PROGRESS.md`, then commit with a message like `M4.2: duplicate groups by time and similarity`.
- If a task turns out bigger than expected, split it into smaller checkboxes in `docs/PLAN.md` before starting.
- Anything on the out-of-scope list in `docs/SPEC.md` needs my explicit approval before you build it.
