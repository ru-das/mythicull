import os
from datetime import datetime

from PIL import Image

from mythicull.ingest import read_metadata
from tests.conftest import make_jpeg


def test_exif_time_and_dimensions(tmp_path):
    p = make_jpeg(tmp_path / "a.jpg", datetime(2025, 6, 14, 14, 5, 9), subsec="25", size=(64, 48))
    m = read_metadata(p)
    assert (m.capture_time, m.time_source) == ("2025-06-14T14:05:09.250", "exif")
    assert (m.width, m.height, m.orientation) == (64, 48, 1)


def test_subsecond_ordering(tmp_path):
    t = datetime(2025, 6, 14, 14, 0, 0)
    a = read_metadata(make_jpeg(tmp_path / "a.jpg", t, subsec="9"))
    b = read_metadata(make_jpeg(tmp_path / "b.jpg", t, subsec="10"))
    c = read_metadata(make_jpeg(tmp_path / "c.jpg", t, subsec="05"))
    # "9" means .9 s, so ordering is c(.05) < b(.10) < a(.90)
    assert c.capture_time < b.capture_time < a.capture_time


def test_mtime_fallback(tmp_path):
    p = make_jpeg(tmp_path / "n.jpg", None)
    os.utime(p, (1_750_000_000, 1_750_000_000))
    m = read_metadata(p)
    assert m.time_source == "mtime"
    assert m.capture_time == datetime.fromtimestamp(1_750_000_000).isoformat(timespec="milliseconds")


def test_modified_datetime_fallback_and_camera_orientation(tmp_path):
    p = tmp_path / "m.jpg"
    exif = Image.Exif()
    exif[0x0132] = "2025:01:02 03:04:05"
    exif[0x010F], exif[0x0110], exif[0x0112] = "ACME", "X100", 6
    Image.new("RGB", (10, 20)).save(p, "JPEG", exif=exif)
    m = read_metadata(p)
    assert (m.capture_time, m.time_source) == ("2025-01-02T03:04:05.000", "exif_modified")
    assert (m.camera_make, m.camera_model, m.orientation) == ("ACME", "X100", 6)


def test_raw_uses_companion_time(tmp_path):
    jpg = make_jpeg(tmp_path / "r.jpg", datetime(2025, 6, 14, 9, 0, 0))
    raw = tmp_path / "r.nef"
    raw.write_bytes(b"not a real raw")
    m = read_metadata(raw, jpg)
    assert m.time_source == "exif" and m.capture_time.startswith("2025-06-14T09:00:00")
    assert (m.width, m.height) == (64, 48)
