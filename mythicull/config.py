import os
from pathlib import Path

MODEL_ID = "google/embeddinggemma-2"
DEFAULT_CHAPTER_GAP_MINUTES = 15
DEFAULT_DUP_THRESHOLD = 0.92
DEFAULT_SEARCH_K = 50


def data_dir() -> Path:
    """Runtime data root. Read per call so tests can set MYTHICULL_DATA_DIR."""
    return Path(os.environ.get("MYTHICULL_DATA_DIR", "~/.mythicull")).expanduser()


def model_dir() -> Path:
    """Where the model lives: inside the data dir, so it survives HF cache cleanups."""
    return data_dir() / "models" / MODEL_ID.replace("/", "--")


def batch_size() -> int:
    return int(os.environ.get("MYTHICULL_BATCH_SIZE", "8"))


def db_path() -> Path:
    return data_dir() / "mythicull.db"
