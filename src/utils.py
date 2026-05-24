from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from src.config import LOG_DIR


def configure_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "gst_invoice_intelligence.log"

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    existing_files = {
        getattr(handler, "baseFilename", None)
        for handler in root.handlers
    }
    if str(log_path) not in existing_files:
        file_handler = RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    if not any(isinstance(handler, logging.StreamHandler) for handler in root.handlers):
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)


def format_currency(value: float | int | None) -> str:
    if value is None:
        return "INR 0"
    return f"INR {float(value):,.2f}"
