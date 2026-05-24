from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from pdf2image import convert_from_path
from PIL import Image


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocumentPage:
    image: np.ndarray
    page_number: int


def sanitize_filename(filename: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    return safe or "invoice"


def save_uploaded_file(uploaded_file: Any, upload_dir: Path) -> Path:
    upload_dir.mkdir(parents=True, exist_ok=True)
    target = upload_dir / sanitize_filename(uploaded_file.name)
    target.write_bytes(uploaded_file.getbuffer())
    logger.info("Saved upload to %s", target)
    return target


def load_document_pages(path: Path) -> list[DocumentPage]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _load_pdf_pages(path)
    return [_load_image_page(path)]


def _load_image_page(path: Path) -> DocumentPage:
    image = cv2.imread(str(path))
    if image is None:
        pil_image = Image.open(path).convert("RGB")
        image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    return DocumentPage(image=image, page_number=1)


def _load_pdf_pages(path: Path) -> list[DocumentPage]:
    try:
        pil_pages = convert_from_path(str(path), dpi=300)
    except Exception as exc:
        logger.info("Poppler PDF conversion failed, trying PyMuPDF fallback: %s", exc)
        return _load_pdf_pages_with_pymupdf(path)

    pages: list[DocumentPage] = []
    for index, pil_page in enumerate(pil_pages, start=1):
        rgb = np.array(pil_page.convert("RGB"))
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        pages.append(DocumentPage(image=bgr, page_number=index))
    return pages


def _load_pdf_pages_with_pymupdf(path: Path) -> list[DocumentPage]:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError(
            "PDF conversion failed. Install Poppler on PATH or install PyMuPDF in the Python environment."
        ) from exc

    pages: list[DocumentPage] = []
    try:
        with fitz.open(path) as document:
            zoom = 300 / 72
            matrix = fitz.Matrix(zoom, zoom)
            for index, page in enumerate(document, start=1):
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                    pixmap.height,
                    pixmap.width,
                    pixmap.n,
                )
                if pixmap.n == 4:
                    image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
                else:
                    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                pages.append(DocumentPage(image=image, page_number=index))
    except Exception as exc:
        raise RuntimeError(f"PDF conversion failed for {path.name}: {exc}") from exc

    if not pages:
        raise RuntimeError(f"PDF conversion failed for {path.name}: no pages found")
    return pages
