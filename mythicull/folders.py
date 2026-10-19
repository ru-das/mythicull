"""Desktop folder selection, isolated from the server's worker threads."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from threading import Lock
from typing import Literal


_dialog_lock = Lock()
UNAVAILABLE = (
    "Folder chooser unavailable. Run MythiCull on your desktop. "
    "On Linux, install Zenity, KDialog or Python Tk support (python3-tk). "
    "You can also enter the folder path manually."
)


def choose_folder(purpose: Literal["import", "export"]) -> str | None:
    """Return a folder, None on cancellation, or a useful desktop-support error."""
    if not _dialog_lock.acquire(blocking=False):
        raise BlockingIOError("A folder chooser is already open. Finish or cancel it first.")
    try:
        if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            raise RuntimeError(UNAVAILABLE)
        title = "Choose photo folder" if purpose == "import" else "Choose export folder"
        # Tk must run on a process's main thread (especially on macOS).
        # Linux desktop tools use the installed GTK/KDE folder dialog when available.
        native = False
        if sys.platform.startswith("linux") and shutil.which("zenity"):
            command = ["zenity", "--file-selection", "--directory", "--title", title]
            native = True
        elif sys.platform.startswith("linux") and shutil.which("kdialog"):
            command = ["kdialog", "--getexistingdirectory", str(Path.home()), "--title", title]
            native = True
        else:
            script = '''
import json
import sys
import tkinter as tk
from tkinter import filedialog

root = tk.Tk()
root.withdraw()
try:
    root.attributes("-topmost", True)
    folder = filedialog.askdirectory(parent=root, title=sys.argv[1], mustexist=True)
    print(json.dumps(folder or None))
finally:
    root.destroy()
'''
            command = [sys.executable, "-c", script, title]
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, encoding="utf-8",
                timeout=300, env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Folder chooser timed out. Choose the folder again.") from exc
        except OSError as exc:
            raise RuntimeError(UNAVAILABLE) from exc
        if native and result.returncode == 1:
            return None
        if result.returncode != 0:
            raise RuntimeError(UNAVAILABLE)
        folder = result.stdout.rstrip("\n") if native else json.loads(result.stdout)
        if not folder:
            return None
        path = Path(folder)
        if not path.is_dir():
            raise RuntimeError("The selected folder is no longer available. Choose another folder.")
        return str(path.resolve())
    finally:
        _dialog_lock.release()
