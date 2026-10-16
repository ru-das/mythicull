from datetime import datetime, timedelta
from pathlib import Path

import pytest
from PIL import Image


def make_jpeg(path: Path, when: datetime | None, subsec: str | None = None, size=(64, 48), color=(120, 80, 40)) -> Path:
    """Write a tiny JPEG; EXIF DateTimeOriginal (+SubSecTimeOriginal) set when `when` is given."""
    img = Image.new("RGB", size, color)
    exif = Image.Exif()
    if when is not None:
        ifd = exif.get_ifd(0x8769)
        ifd[0x9003] = when.strftime("%Y:%m:%d %H:%M:%S")
        if subsec is not None:
            ifd[0x9291] = subsec
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "JPEG", exif=exif)
    return path


@pytest.fixture
def photo_folder(tmp_path: Path) -> Path:
    """Six JPEGs: a burst of three, then a gap of an hour, then three more (one in a subfolder, one uppercase ext)."""
    root = tmp_path / "shoot"
    t0 = datetime(2025, 6, 14, 14, 0, 0)
    offsets = [0, 2, 4, 3600, 3602, 3604]
    names = ["a.jpg", "b.jpg", "c.jpg", "d.jpg", "sub/e.jpg", "F.JPG"]
    for off, name in zip(offsets, names):
        make_jpeg(root / name, t0 + timedelta(seconds=off), subsec="00")
    return root
