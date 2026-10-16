# MythiCull: Progress Log

Claude Code updates this file after every task. Keep it short: replace stale entries instead of appending forever.

## Current state
- Next task: **M0.1 Scaffold** (code done, box not ticked: `pip install -r requirements.txt` not yet verified)
- Last completed: none
- Blockers: none

## Tuned values and model facts
| Item | Value | Source or how it was checked |
| --- | --- | --- |
| Model id | `google/embeddinggemma-2` | |
| Load dtype and device | TBD (M0.2) | |
| Seconds per image | TBD (M0.2) | |
| Search query prompt | TBD (M0.2, from model card) | |
| `chapter_gap_minutes` | 15 (default) | |
| `dup_threshold` | 0.92 (default, untuned) | |
| XMP tested in | TBD (M7.3) | |

## Decisions
<!-- One line each: date, decision, reason. -->

## Dependencies added
fastapi, uvicorn, pydantic, sentence-transformers, torch, rawpy, Pillow, exifread, opencv-python-headless, numpy: stack per AGENTS.md. httpx: FastAPI TestClient. pytest: tests.

## Known issues
- M0.1: `pip install` of `torch`/`sentence-transformers` failed locally with `Disk quota exceeded` (59G free on /home, so likely a per-user quota). All other deps install and `pytest -q` passes. Re-run the full install on a machine with space (or use the CPU torch wheel) and tick M0.1.
<!-- Open problems to fix before the demo. -->

## Demo numbers (M8.1)
- Photos in:
- Chapters:
- Duplicate groups:
- Photos kept:
- Index time:
- Review time:
