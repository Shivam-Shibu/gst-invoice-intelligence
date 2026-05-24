from __future__ import annotations

from pathlib import Path


APP_NAME = "GST Invoice Intelligence"
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
MODEL_DIR = BASE_DIR / "models"
LOG_DIR = BASE_DIR / "outputs" / "logs"


def ensure_directories() -> None:
    for directory in (UPLOAD_DIR, OUTPUT_DIR, MODEL_DIR, LOG_DIR):
        directory.mkdir(parents=True, exist_ok=True)
