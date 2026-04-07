from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def load_image(path: Path) -> np.ndarray:
    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"Unable to load image: {path.name}")
    return image


def crop_layout_regions(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    top_margin = max(int(height * 0.04), 0)
    bottom_margin = max(int(height * 0.02), 0)
    left_margin = max(int(width * 0.03), 0)
    right_margin = max(int(width * 0.02), 0)
    return image[top_margin: height - bottom_margin, left_margin: width - right_margin]


def preprocess_image(path: Path) -> np.ndarray:
    image = load_image(path)
    cropped = crop_layout_regions(image)

    max_width = 2200
    scale = max_width / cropped.shape[1] if cropped.shape[1] < max_width else 1.0
    resized = cv2.resize(cropped, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    grayscale = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    denoised = cv2.GaussianBlur(grayscale, (3, 3), 0)
    thresholded = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )
    return thresholded
