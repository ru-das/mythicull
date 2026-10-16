import exifread

from tests.conftest import make_jpeg  # noqa: F401


def test_fixture_folder_has_exif_times(photo_folder):
    files = sorted(p for p in photo_folder.rglob("*") if p.is_file())
    assert len(files) == 6
    with open(photo_folder / "a.jpg", "rb") as f:
        tags = exifread.process_file(f, details=False)
    assert str(tags["EXIF DateTimeOriginal"]) == "2025:06:14 14:00:00"
    assert str(tags["EXIF SubSecTimeOriginal"]) == "00"
