import json
import subprocess

from fastapi.testclient import TestClient
import pytest

from mythicull import folders
from mythicull.main import app


def test_folder_dialog_results(tmp_path, monkeypatch):
    monkeypatch.setattr(folders.sys, "platform", "win32")
    selected = tmp_path / "婚礼 shoot"
    selected.mkdir()
    result = subprocess.CompletedProcess([], 0, json.dumps(str(selected)), "")

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        assert command[:2] == [folders.sys.executable, "-c"]
        assert kwargs["timeout"] == 300
        assert "shell" not in kwargs
        return result

    monkeypatch.setattr(folders.subprocess, "run", run)
    assert folders.choose_folder("import") == str(selected)
    result.stdout = "null"
    assert folders.choose_folder("export") is None
    result.returncode = 1
    with pytest.raises(RuntimeError, match="Folder chooser unavailable"):
        folders.choose_folder("import")
    result.returncode = 0
    result.stdout = json.dumps(str(tmp_path / "gone"))
    with pytest.raises(RuntimeError, match="no longer available"):
        folders.choose_folder("export")
    folders._dialog_lock.acquire()
    try:
        with pytest.raises(BlockingIOError):
            folders.choose_folder("import")
    finally:
        folders._dialog_lock.release()


@pytest.mark.parametrize("tool", ["zenity", "kdialog"])
def test_linux_dialog_selection_and_cancel(tmp_path, monkeypatch, tool):
    monkeypatch.setattr(folders.sys, "platform", "linux")
    monkeypatch.setenv("DISPLAY", ":1")
    monkeypatch.setattr(folders.shutil, "which", lambda name: name if name == tool else None)
    result = subprocess.CompletedProcess([], 0, str(tmp_path) + "\n", "")

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        assert command[0] == tool
        return result

    monkeypatch.setattr(folders.subprocess, "run", run)
    assert folders.choose_folder("import") == str(tmp_path)
    result.returncode = 1
    assert folders.choose_folder("export") is None
    result.returncode = 255
    with pytest.raises(RuntimeError, match="unavailable"):
        folders.choose_folder("export")


def test_headless_and_timeout_release_lock(monkeypatch):
    monkeypatch.setattr(folders.sys, "platform", "linux")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    with pytest.raises(RuntimeError, match="unavailable"):
        folders.choose_folder("import")
    monkeypatch.setattr(folders.sys, "platform", "darwin")

    def timeout(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        raise subprocess.TimeoutExpired(command, 300)

    monkeypatch.setattr(folders.subprocess, "run", timeout)
    with pytest.raises(RuntimeError, match="timed out"):
        folders.choose_folder("export")
    assert not folders._dialog_lock.locked()


def test_folder_api_local_access_and_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("MYTHICULL_DATA_DIR", str(tmp_path / "data"))
    calls = []

    def choose(purpose: str) -> str | None:
        calls.append(purpose)
        return str(tmp_path) if purpose == "import" else None

    monkeypatch.setattr(folders, "choose_folder", choose)
    with TestClient(app, base_url="http://localhost:8000", client=("127.0.0.1", 1234)) as client:
        for purpose, expected in [("import", str(tmp_path)), ("export", None)]:
            response = client.post("/api/folders/choose", json={"purpose": purpose}, headers={"Origin": "http://localhost:8000"})
            assert response.status_code == 200
            assert response.json() == {"folder": expected}
        for origin in [None, "http://evil.example", "null"]:
            headers = {} if origin is None else {"Origin": origin}
            assert client.post("/api/folders/choose", json={"purpose": "import"}, headers=headers).status_code == 403
        assert calls == ["import", "export"]

        def unavailable(purpose: str) -> str | None:
            raise RuntimeError(folders.UNAVAILABLE)

        monkeypatch.setattr(folders, "choose_folder", unavailable)
        assert client.post("/api/folders/choose", json={"purpose": "import"}, headers={"Origin": "http://localhost:8000"}).status_code == 503
    with TestClient(app, base_url="http://localhost:8000", client=("192.168.1.2", 1234)) as client:
        assert client.post("/api/folders/choose", json={"purpose": "import"}, headers={"Origin": "http://localhost:8000"}).status_code == 403
