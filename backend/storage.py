import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("CAREVOICE_DATA_DIR") or PROJECT_ROOT).expanduser()
UPLOADS_DIR = DATA_DIR / "uploads"
_UPLOAD_CATEGORIES = {"prescriptions", "tablets", "reports"}


def ensure_storage_dirs():
    for category in _UPLOAD_CATEGORIES:
        (UPLOADS_DIR / category).mkdir(parents=True, exist_ok=True)


def upload_path(category, filename):
    if category not in _UPLOAD_CATEGORIES:
        raise ValueError(f"Unsupported upload category: {category}")
    safe_filename = Path(str(filename).replace("\\", "/")).name
    if not safe_filename:
        raise ValueError("Upload filename cannot be empty")
    ensure_storage_dirs()
    return str(UPLOADS_DIR / category / safe_filename)
