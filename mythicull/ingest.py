import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import exifread
from PIL import Image

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
