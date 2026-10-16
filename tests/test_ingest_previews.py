import pytest
from PIL import Image

from mythicull import ingest
from mythicull.ingest import PreviewError, make_previews


def _jpeg(path, size, orientation=None):
    exif = Image.Exif()
    if orientation:
        exif[0x0112] = orientation
    Image.new("RGB", size, (200, 10, 10)).save(path, "JPEG", exif=exif)
    return path


def test_sizes_and_no_upscale(tmp_path):
    big = _jpeg(tmp_path / "big.jpg", (3200, 2000))
    small = _jpeg(tmp_path / "small.jpg", (64, 48))
    t, p = make_previews(big, None, tmp_path / "out", "big")
    assert Image.open(t).size == (320, 200) and Image.open(p).size == (1600, 1000)
    t, p = make_previews(small, None, tmp_path / "out", "small")
    assert Image.open(t).size == Image.open(p).size == (64, 48)


def test_orientation_applied(tmp_path):
    src = _jpeg(tmp_path / "r.jpg", (640, 480), orientation=6)
    t, p = make_previews(src, None, tmp_path / "out", "r", orientation=6)
    assert Image.open(p).size == (480, 640)
    assert Image.open(t).size == (240, 320)


def test_second_run_regenerates_nothing(tmp_path):
    src = _jpeg(tmp_path / "a.jpg", (800, 600))
    t, p = make_previews(src, None, tmp_path / "out", "a")
    before = (t.stat().st_mtime_ns, p.stat().st_mtime_ns)
    src.unlink()  # a second run must not even need the source
    assert make_previews(src, None, tmp_path / "out", "a") == (t, p)
    assert (t.stat().st_mtime_ns, p.stat().st_mtime_ns) == before


def test_raw_uses_larger_of_preview_and_companion(tmp_path, monkeypatch):
    raw = tmp_path / "x.nef"
    raw.write_bytes(b"raw")
    comp = _jpeg(tmp_path / "x.jpg", (1000, 500))
    monkeypatch.setattr(ingest, "_raw_preview", lambda p: Image.new("RGB", (160, 120)))
    _, p = make_previews(raw, comp, tmp_path / "out", "x")
    assert Image.open(p).size == (1000, 500)
    monkeypatch.setattr(ingest, "_raw_preview", lambda p: Image.new("RGB", (2000, 1000)))
    _, p = make_previews(raw, comp, tmp_path / "out", "y")
    assert Image.open(p).size == (1600, 800)


def test_raw_orientation_fallback_for_exifless_preview(tmp_path, monkeypatch):
    raw = tmp_path / "x.nef"
    raw.write_bytes(b"raw")
    monkeypatch.setattr(ingest, "_raw_preview", lambda p: Image.new("RGB", (400, 300)))
    _, p = make_previews(raw, None, tmp_path / "out", "x", orientation=8)
    assert Image.open(p).size == (300, 400)


def test_raw_without_preview_raises(tmp_path):
    raw = tmp_path / "bad.nef"
    raw.write_bytes(b"not a raw")
    with pytest.raises(PreviewError):
        make_previews(raw, None, tmp_path / "out", "bad")
