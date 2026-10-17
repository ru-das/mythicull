from datetime import datetime, timedelta
from pathlib import Path

import pytest
from PIL import Image


def make_jpeg(path: Path, when: datetime | None, subsec: str | None = None, size=(64, 48), color=(120, 80, 40), model: str | None = None) -> Path:
    """Write a tiny JPEG; EXIF DateTimeOriginal (+SubSecTimeOriginal) set when `when` is given."""
    img = Image.new("RGB", size, color)
    exif = Image.Exif()
    if model is not None:
        exif[0x0110] = model
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


class FakeEmbedder:
    """Deterministic 768-d vectors from pixel bytes. `on_batch(n)` runs before each encode (n = 1-based)."""

    model_id = "fake/model"

    def __init__(self, on_batch=None) -> None:
        self.on_batch = on_batch
        self.batches = 0
        self.images_seen = 0

    def encode_images(self, images):
        import hashlib

        import numpy as np

        self.batches += 1
        if self.on_batch:
            self.on_batch(self.batches)
        self.images_seen += len(images)
        out = []
        for im in images:
            seed = int.from_bytes(hashlib.sha256(im.tobytes() + str(im.size).encode()).digest()[:4], "big")
            v = np.random.default_rng(seed).normal(size=768).astype(np.float32)
            out.append(v / np.linalg.norm(v))
        return np.stack(out)

    def encode_text(self, texts):
        import hashlib

        import numpy as np

        out = []
        for t in texts:
            v = np.random.default_rng(int.from_bytes(hashlib.sha256(t.encode()).digest()[:4], "big")).normal(size=768).astype(np.float32)
            out.append(v / np.linalg.norm(v))
        return np.stack(out)
