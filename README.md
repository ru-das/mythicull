# MythiCull

Local-first photo culling for wedding and event photographers. Import a shoot, let it index the photos, then cull with the keyboard. Picks export as XMP sidecars or copied files.

## What it does
- Imports a folder recursively. JPEG, and RAW through the embedded preview. RAW+JPEG pairs are treated as one photo.
- Splits the shoot into story chapters by time gap (default 15 minutes). Chapters with fewer than three photos merge into a neighbour. Chapters can be renamed; renames survive re-runs. After analysis, you can accept suggested chapter names.
- Groups near-duplicate bursts (within 10 s and similar image embedding) and suggests the sharpest frame in each group. The optional “What to look for” description (for example “candid laughter”) and “Suggested photo priority” slider balance sharpness with how well each frame matches the description.
- Per-camera time adjustments for shoots with multiple camera models, without changing the original files or EXIF timestamps.
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

Open http://localhost:8000. On startup, the app offers a one-time model download with progress. Choose **Download model** or **Not now**; **Analyze photos** offers the download again if needed. The model is saved in `~/.mythicull/models/` (inside `MYTHICULL_DATA_DIR`) and loaded from there, so it works offline afterwards. A GPU is strongly recommended: recorded CPU tests ranged from about 8 to 32 s per photo, while a 117-photo GPU run took 123 s including model loading. These are example measurements, not a speed guarantee. Browsing and rating work without the model and before indexing finishes.

Environment variables:
- `MYTHICULL_DATA_DIR`: where projects, thumbnails and embeddings live (default `~/.mythicull`). Never inside a photo folder.
- `MYTHICULL_BATCH_SIZE`: indexing batch size (default 8).

## Usage
1. Create a project: enter a name and use **Choose folder…** to select the photo folder. Import runs in the background.
2. Click **Analyze photos**. Indexing can be cancelled and resumes where it stopped. Time-based chapters are available after import; analysis adds similarity groups and suggested frames. Browsing and rating remain available during analysis.
3. Adjust **Analysis settings** if needed: chapter breaks, **What to look for**, suggestion priority and camera time adjustments (shown for multiple camera models). These preserve your review decisions and renamed chapters.
4. Cull. Suggested view shows one suggestion per group of similar photos; click the count badge to expand a group. Review-state filters show every matching photo. Your last photo, chapter, filter, view and auto-next preference are remembered per project in this browser.
5. The sun/moon button in the top bar switches between dark and light mode. Dark is the default and your choice is remembered in the browser.
6. Use the **Export** panel: write XMP sidecars, or choose a destination folder and copy kept photos (optionally one folder per chapter).

Folder selection opens on the computer running MythiCull. Use the browser on that same desktop via `localhost` or `127.0.0.1`. Windows and macOS use Python's Tk folder dialog; Linux uses Zenity or KDialog when installed, with Tk as a fallback (`python3-tk` on Debian/Ubuntu). If no desktop dialog is available, the UI offers manual path entry. XMP export writes beside the originals and needs no destination selection.

Your photo folder is read-only. The only files MythiCull ever writes there are `.xmp` sidecars, and it will not overwrite one it did not create. Copy export never overwrites files and refuses a destination inside the photo folder.

In the large preview, **Preview pixels** (or **Z**) shows the cached preview at one image pixel per CSS pixel. Scroll, drag with a mouse, or focus the image and use arrows to pan; **Fit photo** returns to the whole frame. The cache is at most 1600px on its long edge, so this does not show original-resolution RAW detail. **Pin reference** keeps one photo visible while you navigate or choose a similar frame from the thumbnail strip. Ratings always apply to the current photo. On phones, the reference and current photo stack vertically. Clear the reference or close the preview to leave comparison.

On narrow screens, **Options** holds Suggested/Every photo and Auto-Next. Successful import details stay collapsed; imports with skipped files show their details. The Rejected view shows photos at normal brightness for a second look.

Export always uses the whole project, including photos outside the current chapter, search and filter. Its preview counts eligibility by file type; missing originals and protected sidecars are checked during export. XMP maps keeps to Green and at least 1 star (0 becomes 1), rejects to Red and 0 stars, and excludes stars-only photos without Keep/Reject. JPEG and DNG are excluded from XMP. Copy export copies kept originals and companions unchanged and records stars in its manifest; it does not embed ratings in the copied files. Clearing a decision does not remove an earlier sidecar.

## Keyboard shortcuts
| Key | Action |
| --- | --- |
| Arrow keys | Move selection; Up/Down move by grid row. In preview, move between photos; when a zoomed image has focus, pan it. |
| Enter / Space | Open or close the large preview |
| Esc | Close preview, or clear search when in the search box |
| P | Keep |
| X | Reject |
| U | Clear decision |
| 0 to 5 | Set stars |
| `/` | Focus the search box |
| Enter (in search box) | Run search |
| Ctrl/Cmd+Z | Undo the last decision (history resets on navigation or reload) |
| Z (in preview) | Toggle fit / cached-preview pixels |

## Limitations
- Search scores are only good for ranking within one query; there is no relevance cut-off.
- Camera time adjustments are keyed by camera model, so two bodies of the same model share one adjustment. Captions still show the original capture time.
- The duplicate threshold (0.92) was tuned on easy burst frames, not a real moving-subject shoot.
- XMP is written for RAW files only (not JPEG or DNG). A RAW+JPEG pair gets one sidecar named after the RAW. Sidecars have not yet been checked in Lightroom Classic or darktable.
- RAW support relies on the embedded preview and is tested with mocks, not real RAW files.
- A sidecar is not removed if you later clear the decision.
- Single user, local only. The photo list is one unpaginated response, fine up to about 3000 photos.
- Not included: face recognition, RAW editing, album layouts, cloud models, accounts.

## Tests
`pytest -q` is fast and never loads the model. `pytest -q -m model` runs the real-model tests.
