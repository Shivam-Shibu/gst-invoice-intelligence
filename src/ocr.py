from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
import pytesseract


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float
    engine: str


class OcrEngine:
    def __init__(self, enable_easyocr: bool = True, languages: list[str] | None = None) -> None:
        self.enable_easyocr = enable_easyocr
        self.languages = languages or ["en"]
        self._easyocr_reader: Any | None = None

    def extract_text(self, image: np.ndarray) -> OcrResult:
        tesseract_result = self._extract_with_tesseract(image)
        if tesseract_result.text.strip() or not self.enable_easyocr:
            return tesseract_result

        easyocr_result = self._extract_with_easyocr(image)
        if easyocr_result is not None:
            return easyocr_result

        return tesseract_result

    def _extract_with_tesseract(self, image: np.ndarray) -> OcrResult:
        try:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            config = "--oem 3 --psm 6"
            text = pytesseract.image_to_string(rgb, config=config)
            data = pytesseract.image_to_data(
                rgb,
                output_type=pytesseract.Output.DICT,
                config=config,
            )
            confidences = []
            for value in data.get("conf", []):
                try:
                    score = float(value)
                except (TypeError, ValueError):
                    continue
                if score >= 0:
                    confidences.append(score)
            confidence = sum(confidences) / len(confidences) if confidences else 0.0
            return OcrResult(text=text, confidence=confidence, engine="pytesseract")
        except Exception as exc:
            logger.warning("pytesseract OCR failed: %s", exc)
            return OcrResult(text="", confidence=0.0, engine="pytesseract")

    def _extract_with_easyocr(self, image: np.ndarray) -> OcrResult | None:
        try:
            import easyocr
        except ImportError:
            logger.info("easyocr is not installed; skipping EasyOCR fallback")
            return None

        try:
            if self._easyocr_reader is None:
                self._easyocr_reader = easyocr.Reader(self.languages, gpu=False)

            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = self._easyocr_reader.readtext(rgb)
            text = "\n".join(item[1] for item in results if len(item) >= 2)
            scores = [float(item[2]) * 100 for item in results if len(item) >= 3]
            confidence = sum(scores) / len(scores) if scores else 0.0
            return OcrResult(text=text, confidence=confidence, engine="easyocr")
        except Exception as exc:
            logger.warning("EasyOCR failed: %s", exc)
            return None
