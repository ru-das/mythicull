# MythiCull: Progress Log

Claude Code updates this file after every task. Keep it short: replace stale entries instead of appending forever.

## Current state
- Next task: **M1.1 Config and database**
- Last completed: M0.2 Model spike
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
<!-- One line each: date, decision, reason. -->

## Dependencies added
fastapi, uvicorn, pydantic, sentence-transformers, torch, rawpy, Pillow, exifread, opencv-python-headless, numpy: stack per AGENTS.md. httpx: FastAPI TestClient. pytest: tests.

## Known issues
- M0.2: query prompt not verified against the model card. 32 s/image on CPU is too slow for a real shoot: re-time on GPU and check batch size and input resolution before M4.2. No NaNs. Top-3 for all three test queries were from the matching category folder.
<!-- Open problems to fix before the demo. -->

## Demo numbers (M8.1)
- Photos in:
- Chapters:
- Duplicate groups:
- Photos kept:
- Index time:
- Review time:
