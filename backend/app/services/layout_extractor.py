from __future__ import annotations

import re
from pathlib import Path

import cv2
import numpy as np

from app.schemas import ExtractedRow
from app.services.ocr import ocr_service
from app.services.parser import error_row


def _crop(image: np.ndarray, region: tuple[float, float, float, float]) -> np.ndarray:
    height, width = image.shape[:2]
    x1, y1, x2, y2 = region
    return image[int(height * y1): int(height * y2), int(width * x1): int(width * x2)]


def _clean(value: str) -> str | None:
    cleaned = re.sub(r"\s+", " ", value).strip(" |[](){}:_-")
    return cleaned or None


def _normalize_number(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
    return match.group(0) if match else _clean(value)


def _extract_crop_text(
    image: np.ndarray,
    region: tuple[float, float, float, float],
    *,
    config: str = "--psm 7",
    scale: int = 5,
    threshold: bool = False,
) -> tuple[str | None, float]:
    crop = _crop(image, region)
    text, confidence = ocr_service.extract_crop_text(crop, config=config, scale=scale, threshold=threshold)
    return _clean(text), confidence


def _extract_numeric_crop(
    image: np.ndarray,
    region: tuple[float, float, float, float],
    *,
    scale: int = 6,
) -> tuple[str | None, float]:
    text, confidence = _extract_crop_text(
        image,
        region,
        config="--psm 7 -c tessedit_char_whitelist=0123456789.-",
        scale=scale,
        threshold=True,
    )
    return _normalize_number(text), confidence


def _extract_checkbox(image: np.ndarray, region: tuple[float, float, float, float]) -> bool:
    crop = _crop(image, region)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
    fill_ratio = float(np.count_nonzero(binary)) / float(binary.size or 1)
    return fill_ratio > 0.12


def _join(values: list[str | None]) -> str | None:
    cleaned = [value for value in (_clean(item or "") for item in values) if value]
    return " | ".join(cleaned) if cleaned else None


def _extract_table_row(
    image: np.ndarray,
    row_region: tuple[float, float, float, float],
    columns: dict[str, tuple[float, float, float, float]],
) -> tuple[dict[str, str | None], float]:
    row_image = _crop(image, row_region)
    confidences: list[float] = []
    result: dict[str, str | None] = {}
    for key, region in columns.items():
        if key in {"count", "rate_per_kg", "rate_incl_gst", "gst", "epi_on_loom", "ppi"}:
            value, confidence = _extract_numeric_crop(row_image, region)
        else:
            value, confidence = _extract_crop_text(row_image, region, scale=4, threshold=False)
        result[key] = value
        confidences.append(confidence)
    average_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0
    return result, average_confidence


def _extract_particular_row(
    image: np.ndarray,
    region: tuple[float, float, float, float],
) -> tuple[str | None, str | None]:
    row_image = _crop(image, region)
    rate, _ = _extract_crop_text(
        row_image,
        (0.33, 0.0, 0.64, 1.0),
        config="--psm 7",
        scale=5,
        threshold=False,
    )
    cost, _ = _extract_crop_text(
        row_image,
        (0.64, 0.0, 0.98, 1.0),
        config="--psm 7",
        scale=5,
        threshold=False,
    )
    return _normalize_number(rate) or rate, _normalize_number(cost) or cost


def extract_layout_fields(image_path: Path) -> ExtractedRow:
    image = cv2.imread(str(image_path))
    if image is None:
        return error_row(image_path, "Unable to load image.")

    row = ExtractedRow(
        image_name=image_path.name,
        source_file=image_path.name,
        ocr_engine="tesseract-layout",
    )
    confidences: list[float] = []

    top_fields = {
        "date": ((0.065, 0.08, 0.18, 0.14), True),
        "agent": ((0.205, 0.07, 0.34, 0.13), False),
        "customer": ((0.405, 0.07, 0.56, 0.13), False),
        "sourcing_executive": ((0.635, 0.07, 0.76, 0.13), False),
        "weave": ((0.89, 0.07, 0.985, 0.13), False),
        "quality": ((0.045, 0.145, 0.18, 0.235), False),
        "shafts": ((0.205, 0.145, 0.31, 0.21), False),
        "marketing_executive": ((0.405, 0.145, 0.545, 0.21), False),
        "buyer_reference_no": ((0.64, 0.145, 0.79, 0.21), False),
        "design_no": ((0.875, 0.145, 0.985, 0.21), False),
    }
    for field_name, (region, numeric) in top_fields.items():
        if numeric:
            value, confidence = _extract_numeric_crop(image, region)
        else:
            value, confidence = _extract_crop_text(image, region, config="--psm 6" if field_name == "quality" else "--psm 7", scale=5)
        setattr(row, field_name, value)
        confidences.append(confidence)

    row.is_warp_butta = _extract_checkbox(image, (0.12, 0.212, 0.135, 0.235))
    row.is_weft_butta = _extract_checkbox(image, (0.275, 0.212, 0.29, 0.235))
    row.is_warp2_sizing_count = _extract_checkbox(image, (0.43, 0.212, 0.445, 0.235))
    row.is_seersucker = _extract_checkbox(image, (0.595, 0.212, 0.61, 0.235))

    yarn_columns = {
        "count": (0.21, 0.0, 0.265, 1.0),
        "rate_per_kg": (0.265, 0.0, 0.345, 1.0),
        "rate_incl_gst": (0.345, 0.0, 0.455, 1.0),
        "gst": (0.455, 0.0, 0.515, 1.0),
        "content": (0.515, 0.0, 0.60, 1.0),
        "yarn_type": (0.60, 0.0, 0.70, 1.0),
        "mill": (0.70, 0.0, 0.77, 1.0),
        "epi_on_loom": (0.77, 0.0, 0.875, 1.0),
        "ppi": (0.875, 0.0, 0.955, 1.0),
    }
    warp_regions = [
        (0.02, 0.367, 0.57, 0.402),
        (0.02, 0.402, 0.57, 0.437),
        (0.02, 0.437, 0.57, 0.472),
    ]
    weft_region = (0.02, 0.467, 0.57, 0.505)

    warp_rows: list[dict[str, str | None]] = []
    for region in warp_regions:
        values, confidence = _extract_table_row(image, region, yarn_columns)
        if any(values.get(key) for key in ("count", "rate_per_kg", "rate_incl_gst")):
            warp_rows.append(values)
            confidences.append(confidence)

    weft_values, confidence = _extract_table_row(image, weft_region, yarn_columns)
    confidences.append(confidence)

    row.warp_count = _join([item.get("count") for item in warp_rows])
    row.warp_rate_per_kg = _join([item.get("rate_per_kg") for item in warp_rows])
    row.warp_rate_incl_gst = _join([item.get("rate_incl_gst") for item in warp_rows])
    row.warp_gst = _join([item.get("gst") for item in warp_rows])
    row.warp_content = _join([item.get("content") for item in warp_rows])
    row.warp_yarn_type = _join([item.get("yarn_type") for item in warp_rows])
    row.warp_mill = _join([item.get("mill") for item in warp_rows])
    row.warp_epi_on_loom = _join([item.get("epi_on_loom") for item in warp_rows])

    row.weft_count = weft_values.get("count")
    row.weft_rate_per_kg = weft_values.get("rate_per_kg")
    row.weft_rate_incl_gst = weft_values.get("rate_incl_gst")
    row.weft_gst = weft_values.get("gst")
    row.weft_content = weft_values.get("content")
    row.weft_yarn_type = weft_values.get("yarn_type")
    row.weft_mill = weft_values.get("mill")
    row.weft_ppi = weft_values.get("ppi")

    right_metric_fields = {
        "grey_width": (0.71, 0.327, 0.78, 0.36),
        "epi_on_table": (0.71, 0.356, 0.79, 0.39),
        "meters_per_120_yards": (0.71, 0.418, 0.80, 0.452),
        "total_ends": (0.71, 0.454, 0.805, 0.488),
        "epi_difference": (0.90, 0.327, 0.965, 0.36),
        "reed_space": (0.90, 0.358, 0.965, 0.39),
        "warp_crimp_percent": (0.90, 0.418, 0.965, 0.452),
    }
    for field_name, region in right_metric_fields.items():
        value, confidence = _extract_numeric_crop(image, region)
        setattr(row, field_name, value)
        confidences.append(confidence)

    lower_left_fields = {
        "weight_warp1": (0.08, 0.604, 0.125, 0.638),
        "cost_warp1": (0.14, 0.604, 0.19, 0.638),
        "composition_warp1": (0.19, 0.604, 0.255, 0.638),
        "weight_weft1": (0.08, 0.688, 0.125, 0.722),
        "cost_weft1": (0.14, 0.688, 0.19, 0.722),
        "composition_weft1": (0.19, 0.688, 0.255, 0.722),
        "gsm_total_yarn_cost": (0.085, 0.739, 0.135, 0.773),
        "fabric_total_yarn_cost": (0.14, 0.739, 0.198, 0.773),
        "fabric_weight_glm_inc_sizing": (0.085, 0.793, 0.145, 0.827),
    }
    for field_name, region in lower_left_fields.items():
        value, confidence = _extract_numeric_crop(image, region)
        setattr(row, field_name, value)
        confidences.append(confidence)

    particular_regions = {
        "sizing_per_kg": (0.255, 0.581, 0.74, 0.614),
        "weaving_charges": (0.255, 0.616, 0.74, 0.649),
        "freight": (0.255, 0.652, 0.74, 0.685),
        "butta_cutting": (0.255, 0.688, 0.74, 0.721),
        "yarn_wastage": (0.255, 0.724, 0.74, 0.757),
        "value_loss_interest": (0.255, 0.759, 0.74, 0.792),
        "payment_term": (0.255, 0.796, 0.74, 0.829),
        "particulars_total": (0.255, 0.832, 0.74, 0.865),
        "commission_cd": (0.255, 0.87, 0.74, 0.903),
        "remark": (0.255, 0.907, 0.74, 0.939),
        "other_cost_if_any": (0.255, 0.947, 0.74, 0.979),
        "extra_remarks_if_any": (0.255, 0.979, 0.74, 1.0),
    }

    row.sizing_per_kg_rate, row.sizing_per_kg_cost = _extract_particular_row(image, particular_regions["sizing_per_kg"])
    row.weaving_charges_rate, row.weaving_charges_cost = _extract_particular_row(image, particular_regions["weaving_charges"])
    row.freight_rate, row.freight_cost = _extract_particular_row(image, particular_regions["freight"])
    row.butta_cutting_rate, row.butta_cutting_cost = _extract_particular_row(image, particular_regions["butta_cutting"])
    row.yarn_wastage_rate, row.yarn_wastage_cost = _extract_particular_row(image, particular_regions["yarn_wastage"])
    row.value_loss_interest_rate, row.value_loss_interest_cost = _extract_particular_row(image, particular_regions["value_loss_interest"])
    row.commission_cd_rate, row.commission_cd_cost = _extract_particular_row(image, particular_regions["commission_cd"])

    row.payment_term, conf = _extract_crop_text(image, particular_regions["payment_term"], config="--psm 7", scale=5)
    confidences.append(conf)
    row.particulars_total_cost, conf = _extract_crop_text(image, particular_regions["particulars_total"], config="--psm 7", scale=5)
    confidences.append(conf)
    row.remark, conf = _extract_crop_text(image, particular_regions["remark"], config="--psm 7", scale=5)
    confidences.append(conf)
    row.other_cost_if_any_rate, row.other_cost_if_any_remarks = (
        _extract_particular_row(image, particular_regions["other_cost_if_any"])
    )
    row.extra_remarks_if_any, conf = _extract_crop_text(
        image,
        particular_regions["extra_remarks_if_any"],
        config="--psm 6",
        scale=5,
    )
    confidences.append(conf)

    right_cost_fields = {
        "total_price": (0.885, 0.548, 0.955, 0.58),
        "target_price": (0.885, 0.582, 0.955, 0.614),
        "weaving_charge_as_per_tp": (0.885, 0.616, 0.955, 0.648),
        "order_quantity": (0.885, 0.651, 0.965, 0.684),
        "yarn_requirement_warp1": (0.885, 0.688, 0.955, 0.72),
        "yarn_requirement_weft1": (0.885, 0.758, 0.955, 0.79),
        "yarn_requirement_total": (0.885, 0.829, 0.955, 0.861),
        "cover_factor": (0.885, 0.9, 0.955, 0.932),
    }
    for field_name, region in right_cost_fields.items():
        value, confidence = _extract_numeric_crop(image, region)
        setattr(row, field_name, value)
        confidences.append(confidence)

    if row.quality:
        row.quality = row.quality.replace("lity", "").strip()

    important_fields = [
        "date",
        "agent",
        "customer",
        "quality",
        "warp_count",
        "weft_count",
        "total_price",
        "target_price",
        "order_quantity",
        "yarn_requirement_total",
    ]
    row.low_confidence_fields = [field for field in important_fields if getattr(row, field, None) in (None, "", [])]
    row.ocr_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0
    if row.low_confidence_fields:
        row.status = "REVIEW"
    return row
