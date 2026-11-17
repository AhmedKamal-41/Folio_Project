import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_DIR / "static"
MAX_UPLOAD_BYTES = 1024 * 1024
MAX_REQUEST_BYTES = 2 * MAX_UPLOAD_BYTES
MAX_CONTENT_CHARACTERS = 100000
MAX_CONTENT_OPERATIONS = 5000


@dataclass(frozen=True)
class Settings:
    database_path: Path


def load_settings(database_path=None):
    path = database_path or os.getenv("DATABASE_PATH", PROJECT_DIR / "data" / "folio.db")
    return Settings(database_path=Path(path))
