# MythiCull

Local-first photo culling for wedding and event photographers. Import a shoot, let it index the photos, then cull with the keyboard. Picks export as XMP sidecars or copied files.

## What it does
- Imports a folder recursively. JPEG, and RAW through the embedded preview. RAW+JPEG pairs are treated as one photo.
- Splits the shoot into story chapters by time gap (default 15 minutes). Chapters can be renamed; renames survive re-runs.
- Groups near-duplicate bursts (within 10 s and similar image embedding) and suggests the sharpest frame in each group. An optional vibe text (for example "candid laughter") and a Sharp/Vibe slider in the sidebar blend sharpness with how well each frame matches the text when choosing the pick.
- Plain-English search ("people dancing") ranked with image embeddings.
- Keep / reject / star review with filters, counters and undo.
- Exports XMP sidecars (stars and colour label) for RAW files, or copies the kept photos to a new folder.

## Why an open-weight model
It uses the open-weight `google/embeddinggemma-2` model, run on your own machine.
- Privacy: photos never leave your computer. There is no telemetry and no cloud API.
- Offline: after the one-time model download it works with no network.
- No per-image cost: indexing a 3000-photo shoot costs electricity, not API fees.
- No outside requests from the page either: the fonts are bundled in `web/fonts/`.

## Setup
Python 3.11+.

```
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn mythicull.main:app --port 8000
```

Open http://localhost:8000. The first time you click Index photos, the app shows a one-time model download with progress. The model is saved in `~/.mythicull/models/` (inside `MYTHICULL_DATA_DIR`) and loaded from there, so it works offline afterwards. A GPU is strongly recommended: indexing took about 32 s per photo on a CPU in our test and about 1 s or less on a GPU. Browsing and rating work without the model and before indexing finishes.

Environment variables:
- `MYTHICULL_DATA_DIR`: where projects, thumbnails and embeddings live (default `~/.mythicull`). Never inside a photo folder.
- `MYTHICULL_BATCH_SIZE`: indexing batch size (default 8).

## Usage
1. Create a project: enter a name and use **Choose folder…** to select the photo folder. Import runs in the background.
2. Click **Index photos**. Indexing can be cancelled and resumes where it stopped. Chapters and Best/All grouping appear when it finishes.
3. Cull. Best view shows one pick per duplicate group; click the count badge to expand a group.
4. The sun/moon button in the top bar switches between dark and light mode. Dark is the default and your choice is remembered in the browser.
5. Use the **Export** panel: write XMP sidecars, or choose a destination folder and copy kept photos (optionally one folder per chapter).

Folder selection opens on the computer running MythiCull. Use the browser on that same desktop via `localhost` or `127.0.0.1`. Windows and macOS use Python's Tk folder dialog; Linux uses Zenity or KDialog when installed, with Tk as a fallback (`python3-tk` on Debian/Ubuntu). If no desktop dialog is available, the UI offers manual path entry. XMP export writes beside the originals and needs no destination selection.

Your photo folder is read-only. The only files MythiCull ever writes there are `.xmp` sidecars, and it will not overwrite one it did not create. Copy export never overwrites files and refuses a destination inside the photo folder.

## Keyboard shortcuts
| Key | Action |
| --- | --- |
| Arrow keys | Move selection (or photo, when the preview is open) |
| Enter / Space | Open or close the large preview |
| Esc | Close preview, or clear search when in the search box |
| P | Keep |
| X | Reject |
| U | Clear decision |
| 0 to 5 | Set stars |
| `/` | Focus the search box |
| Enter (in search box) | Run search |
| Ctrl/Cmd+Z | Undo the last decision (lost on page reload) |

## Limitations
- Search scores are only good for ranking within one query; there is no relevance cut-off.
- The duplicate threshold (0.92) was tuned on easy burst frames, not a real moving-subject shoot.
- XMP is written for RAW files only (not JPEG or DNG). A RAW+JPEG pair gets one sidecar named after the RAW. Sidecars have not yet been checked in Lightroom Classic or darktable.
- RAW support relies on the embedded preview and is tested with mocks, not real RAW files.
- A sidecar is not removed if you later clear the decision.
- Single user, local only. The photo list is one unpaginated response, fine up to about 3000 photos.
- Not included: face recognition, RAW editing, album layouts, cloud models, accounts.

## Tests
`pytest -q` is fast and never loads the model. `pytest -q -m model` runs the real-model tests.
