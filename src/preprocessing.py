from __future__ import annotations

import cv2
import numpy as np


def preprocess_image(image: np.ndarray) -> np.ndarray:
    """Prepare invoice scans for OCR while preserving text edges."""
    resized = _resize_for_ocr(image)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=12)
    normalized = cv2.normalize(denoised, None, 0, 255, cv2.NORM_MINMAX)
    thresholded = cv2.adaptiveThreshold(
        normalized,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )
    kernel = np.ones((1, 1), np.uint8)
    opened = cv2.morphologyEx(thresholded, cv2.MORPH_OPEN, kernel)
    return cv2.cvtColor(opened, cv2.COLOR_GRAY2BGR)


def _resize_for_ocr(image: np.ndarray, min_width: int = 1600) -> np.ndarray:
    height, width = image.shape[:2]
    if width >= min_width:
        return image
    scale = min_width / max(width, 1)
    target_size = (int(width * scale), int(height * scale))
    return cv2.resize(image, target_size, interpolation=cv2.INTER_CUBIC)
