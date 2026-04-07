from __future__ import annotations

import re
from pathlib import Path

import cv2
import numpy as np

from app.schemas import ExtractedRow
from app.services.ocr import ocr_service
from app.services.parser import FIELD_PATTERNS, error_row, parse_structured_text


def _crop(image: np.ndarray, region: tuple[float, float, float, float]) -> np.ndarray:
    height, width = image.shape[:2]
    x1, y1, x2, y2 = region
    return image[int(height * y1): int(height * y2), int(width * x1): int(width * x2)]


def _clean(value: str) -> str | None:
    stripped = re.sub(r"\s+", " ", value).strip(" |[](){}:_-")
    return stripped or None


def _clean_entity(value: str) -> str | None:
    cleaned = _clean(value or "")
    if not cleaned:
        return None
    return cleaned.rstrip(".,~")


def _clean_date(value: str) -> str | None:
    cleaned = _clean(value or "")
    if not cleaned:
        return None
    cleaned = re.sub(r"\s*/\s*", "/", cleaned)
    return cleaned


def _extract_numeric(value: str) -> str | None:
    match = re.search(r"(\d+(?:\.\d+)?)", value)
    return match.group(1) if match else None


def _extract_after_label(value: str, labels: list[str]) -> str | None:
    for label in labels:
        pattern = rf"{label}\s*[:\-\]]?\s*([A-Z0-9./&(),+%\"' -]+)"
        match = re.search(pattern, value, flags=re.IGNORECASE)
        if match:
            return _clean(match.group(1))
    return None


def _box_text(image: np.ndarray, region: tuple[float, float, float, float], *, config: str, scale: int = 4, threshold: bool = False) -> tuple[str, float]:
    crop = _crop(image, region)
    text, confidence = ocr_service.extract_crop_text(crop, config=config, scale=scale, threshold=threshold)
    return text, confidence


def _band_text(image: np.ndarray, region: tuple[float, float, float, float]) -> tuple[str, float]:
    return _box_text(image, region, config="--psm 6", scale=6, threshold=False)


def _numeric_from_neighbor_bands(bands: list[str], label: str) -> str | None:
    for index, band in enumerate(bands):
        if label.lower() in band.lower():
            current = _extract_numeric(band)
            if current:
                return current
            if index + 1 < len(bands):
                nearby = _extract_numeric(bands[index + 1])
                if nearby:
                    return nearby
    return None


def _collect_yarn_values(bands: list[str]) -> str | None:
    combined = " ".join(bands)
    pairs = re.findall(r"(WARP\d*|WEFT\d*|TOTAL)\s*([0-9]+(?:\.\d+)?)", combined, flags=re.IGNORECASE)
    if not pairs:
        return None
    formatted = [f"{label.upper()}: {value}" for label, value in pairs]
    return ", ".join(formatted)


def extract_layout_fields(image_path: Path) -> ExtractedRow:
    image = cv2.imread(str(image_path))
    if image is None:
        return error_row(image_path, "Unable to load image.")

    row = ExtractedRow(image_name=image_path.name, ocr_engine="tesseract-layout")
    confidences: list[float] = []

    date_text, conf = _box_text(
        image,
        (0.07, 0.084, 0.18, 0.14),
        config="--psm 7 -c tessedit_char_whitelist=0123456789/-.",
        scale=5,
        threshold=True,
    )
    row.date = _clean_date(date_text)
    confidences.append(conf)

    agent_text, conf = _box_text(image, (0.205, 0.07, 0.34, 0.13), config="--psm 7", scale=4)
    row.agent = _clean_entity(agent_text)
    confidences.append(conf)

    customer_text, conf = _box_text(image, (0.405, 0.07, 0.56, 0.13), config="--psm 7", scale=4)
    row.customer = _clean_entity(customer_text)
    confidences.append(conf)

    quality_text, conf = _box_text(image, (0.045, 0.145, 0.18, 0.235), config="--psm 6", scale=5)
    quality_clean = _clean(quality_text.replace("lity", "").replace("Quality", ""))
    row.quality = quality_clean
    confidences.append(conf)

    top_fallback_text, fallback_conf = _band_text(image, (0.03, 0.05, 0.97, 0.26))
    fallback_row = parse_structured_text(image_path.name, top_fallback_text, fallback_conf, "tesseract-band")

    right_bands: list[str] = []
    for index in range(11):
        y1 = 0.535 + index * 0.022
        y2 = y1 + 0.035
        text, conf = _band_text(image, (0.74, y1, 0.985, y2))
        right_bands.append(text)
        confidences.append(conf)
    right_text = "\n".join(right_bands)

    row.total_price = (
        _extract_after_label(right_text, ["TOTAL PRICE"])
        or _numeric_from_neighbor_bands(right_bands, "TOTAL PRICE")
    )
    row.target_price = (
        _extract_after_label(right_text, ["TARGET PRICE"])
        or _numeric_from_neighbor_bands(right_bands, "TARGET PRICE")
    )
    row.order_quantity = (
        _extract_after_label(right_text, ["ORDER QUANTITY"])
        or _numeric_from_neighbor_bands(right_bands, "ORDER QUANTITY")
    )

    row.yarn_requirement = _collect_yarn_values(right_bands)

    bottom_left_text, conf = _band_text(image, (0.02, 0.58, 0.24, 0.80))
    confidences.append(conf)
    bottom_mid_text, conf = _band_text(image, (0.24, 0.58, 0.74, 0.80))
    confidences.append(conf)

    row.gsm_fabric_weight = _extract_after_label(bottom_left_text, ["FABRIC WEIGHT", "GLM INC. SIZING"]) or fallback_row.gsm_fabric_weight
    if quality_clean and any(keyword in quality_clean.upper() for keyword in ["COTTON", "LINEN", "VISCOSE", "PC", "BCI"]):
        row.composition = quality_clean
    else:
        row.composition = fallback_row.composition

    counts_from_quality = re.findall(r"(\d+\*\d+|\d+/\d+)", quality_clean or "")
    if counts_from_quality:
        row.warp_counts = counts_from_quality[0]
        if len(counts_from_quality) > 1:
            row.weft_counts = counts_from_quality[1]

    if not row.warp_counts:
        row.warp_counts = fallback_row.warp_counts
    if not row.weft_counts:
        row.weft_counts = fallback_row.weft_counts

    low_confidence_fields = []
    for field_name in FIELD_PATTERNS:
        if not getattr(row, field_name, None):
            fallback_value = getattr(fallback_row, field_name, None)
            if fallback_value:
                setattr(row, field_name, fallback_value)
            else:
                low_confidence_fields.append(field_name)

    row.low_confidence_fields = low_confidence_fields
    row.ocr_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0
    if low_confidence_fields:
        row.status = "REVIEW"
    return row
