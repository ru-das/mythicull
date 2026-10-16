from pathlib import Path

from mythicull.ingest import scan_folder


def touch(p: Path) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")
    return p


def test_fixture_folder_recursive_mixed_case(photo_folder):
    res = scan_folder(photo_folder)
    assert sorted(i.path.name for i in res.items) == ["F.JPG", "a.jpg", "b.jpg", "c.jpg", "d.jpg", "e.jpg"]
    assert res.skipped == []


def test_raw_jpeg_pairing(tmp_path):
    raw = touch(tmp_path / "IMG_1.CR2")
    jpg = touch(tmp_path / "img_1.jpg")
    touch(tmp_path / "other" / "IMG_1.jpg")  # different folder: not paired
    res = scan_folder(tmp_path)
    assert len(res.items) == 2
    paired = next(i for i in res.items if i.companion_path)
    assert (paired.path, paired.companion_path) == (raw, jpg)


def test_skips_unsupported_and_unreadable(tmp_path):
    touch(tmp_path / "ok.jpg")
    touch(tmp_path / "notes.txt")
    (tmp_path / "broken.jpg").symlink_to(tmp_path / "missing.jpg")
    res = scan_folder(tmp_path)
    assert [i.path.name for i in res.items] == ["ok.jpg"]
    reasons = {p.name: r for p, r in res.skipped}
    assert reasons["notes.txt"] == "unsupported extension"
    assert reasons["broken.jpg"].startswith("unreadable")
