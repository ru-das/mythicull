import io
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import exifread
from PIL import Image, ImageOps

JPEG_EXTS = {".jpg", ".jpeg"}
RAW_EXTS = {".cr2", ".cr3", ".nef", ".arw", ".raf", ".dng"}


@dataclass
class ScanItem:
    path: Path  # original: the RAW when paired, else the JPEG
    companion_path: Path | None = None


@dataclass
class ScanResult:
    items: list[ScanItem] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)


def scan_folder(root: Path) -> ScanResult:
    """Recursively find supported photos, pairing RAW+JPEG by folder and basename. Read-only."""
    result = ScanResult()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        raws: dict[str, Path] = {}
        jpegs: dict[str, Path] = {}
        for name in sorted(filenames):
            p = Path(dirpath) / name
            ext = p.suffix.lower()
            if ext not in JPEG_EXTS and ext not in RAW_EXTS:
                result.skipped.append((p, "unsupported extension"))
                continue
            try:
                with open(p, "rb") as f:
                    f.read(1)
            except OSError as e:
                result.skipped.append((p, f"unreadable: {e.strerror or e}"))
                continue
            (jpegs if ext in JPEG_EXTS else raws)[p.stem.lower()] = p
        for stem, raw in raws.items():
            result.items.append(ScanItem(raw, jpegs.pop(stem, None)))
        result.items.extend(ScanItem(j) for j in jpegs.values())
    result.items.sort(key=lambda i: str(i.path))
    return result


@dataclass
class PhotoMeta:
    file_size: int
    mtime: float
    camera_make: str | None
    camera_model: str | None
    capture_time: str | None  # naive local ISO, always millisecond precision so it sorts as text
    time_source: str  # "exif", "exif_modified" (Image DateTime) or "mtime" (untrustworthy)
    width: int | None
    height: int | None
    orientation: int  # EXIF code 1-8, 1 when missing


def _exif_tags(path: Path) -> dict:
    try:
        with open(path, "rb") as f:
            return exifread.process_file(f, details=False)
    except Exception:
        return {}


def _tag_text(tags: dict, name: str) -> str | None:
    t = tags.get(name)
    s = str(t).strip().strip("\x00") if t is not None else ""
    return s or None


def _exif_time(tags: dict) -> tuple[str, str] | None:
    for dt_tag, sub_tag, source in (
        ("EXIF DateTimeOriginal", "EXIF SubSecTimeOriginal", "exif"),
        ("Image DateTime", "EXIF SubSecTime", "exif_modified"),
    ):
        raw = _tag_text(tags, dt_tag)
        if not raw:
            continue
        try:
            when = datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
        except ValueError:
            continue
        sub = _tag_text(tags, sub_tag)
        if sub and sub.isdigit():
            when = when.replace(microsecond=int(sub[:6].ljust(6, "0")))
        return when.isoformat(timespec="milliseconds"), source
    return None


def _dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        if path.suffix.lower() in RAW_EXTS:
            import rawpy

            with rawpy.imread(str(path)) as raw:
                return raw.sizes.width, raw.sizes.height
        with Image.open(path) as img:
            return img.size
    except Exception:
        return None, None


def read_metadata(path: Path, companion_path: Path | None = None) -> PhotoMeta:
    """Read-only. Capture time: EXIF original, then EXIF modified, then file mtime. A RAW falls back to its JPEG companion for tags."""
    st = path.stat()
    tags = _exif_tags(path)
    found = _exif_time(tags)
    if companion_path is not None:
        ctags = _exif_tags(companion_path)
        cfound = _exif_time(ctags)
        if found is None and cfound is not None:
            found, tags = cfound, ctags
    if found is None:
        found = (datetime.fromtimestamp(st.st_mtime).isoformat(timespec="milliseconds"), "mtime")
    width, height = _dimensions(path)
    if width is None and companion_path is not None:
        width, height = _dimensions(companion_path)
    orient = tags.get("Image Orientation")
    return PhotoMeta(
        file_size=st.st_size,
        mtime=st.st_mtime,
        camera_make=_tag_text(tags, "Image Make"),
        camera_model=_tag_text(tags, "Image Model"),
        capture_time=found[0],
        time_source=found[1],
        width=width,
        height=height,
        orientation=orient.values[0] if orient is not None and orient.values else 1,
    )


THUMB_EDGE = 320
PREVIEW_EDGE = 1600


class PreviewError(Exception):
    """No usable preview could be produced for a photo."""


def _raw_preview(path: Path) -> Image.Image:
    import rawpy

    try:
        with rawpy.imread(str(path)) as raw:
            thumb = raw.extract_thumb()
    except Exception as e:
        raise PreviewError(f"no embedded preview: {e}") from e
    if thumb.format == rawpy.ThumbFormat.JPEG:
        img = Image.open(io.BytesIO(thumb.data))
    elif thumb.format == rawpy.ThumbFormat.BITMAP:
        img = Image.fromarray(thumb.data)
    else:
        raise PreviewError("unsupported embedded preview format")
    img.load()
    return img


def _load_source(path: Path, companion_path: Path | None) -> Image.Image:
    """Largest available image: JPEG itself, or the bigger of RAW embedded preview and JPEG companion."""
    if path.suffix.lower() not in RAW_EXTS:
        img = Image.open(path)
        img.load()
        return img
    candidates: list[Image.Image] = []
    errors: list[str] = []
    for load in (lambda: _raw_preview(path), lambda: Image.open(companion_path) if companion_path else None):
        try:
            img = load()
            if img is not None:
                img.load()
                candidates.append(img)
        except Exception as e:
            errors.append(str(e))
    if not candidates:
        raise PreviewError("; ".join(errors) or "no usable preview")
    return max(candidates, key=lambda i: i.width * i.height)


_TRANSPOSE = {
    2: Image.Transpose.FLIP_LEFT_RIGHT,
    3: Image.Transpose.ROTATE_180,
    4: Image.Transpose.FLIP_TOP_BOTTOM,
    5: Image.Transpose.TRANSPOSE,
    6: Image.Transpose.ROTATE_270,
    7: Image.Transpose.TRANSVERSE,
    8: Image.Transpose.ROTATE_90,
}


def _apply_orientation(img: Image.Image, fallback: int) -> Image.Image:
    # Embedded RAW previews often carry no EXIF, so fall back to the orientation read from the original.
    if img.getexif().get(0x0112) is None and fallback in _TRANSPOSE:
        return img.transpose(_TRANSPOSE[fallback])
    return ImageOps.exif_transpose(img)


def _save_jpeg(img: Image.Image, dest: Path, edge: int) -> None:
    out = img.copy()
    out.thumbnail((edge, edge))  # only ever shrinks
    tmp = dest.with_name(dest.name + ".tmp")
    out.convert("RGB").save(tmp, "JPEG", quality=85)
    os.replace(tmp, dest)


def make_previews(
    path: Path, companion_path: Path | None, out_dir: Path, photo_id: str, orientation: int = 1
) -> tuple[Path, Path]:
    """Write thumb (320 px) and preview (1600 px) JPEGs into out_dir. Existing files are never regenerated."""
    thumb, preview = out_dir / f"{photo_id}_thumb.jpg", out_dir / f"{photo_id}_preview.jpg"
    if thumb.exists() and preview.exists():
        return thumb, preview
    out_dir.mkdir(parents=True, exist_ok=True)
    img = _apply_orientation(_load_source(path, companion_path), orientation)
    _save_jpeg(img, preview, PREVIEW_EDGE)
    _save_jpeg(img, thumb, THUMB_EDGE)
    return thumb, preview
