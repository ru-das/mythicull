import os
from dataclasses import dataclass, field
from pathlib import Path

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
