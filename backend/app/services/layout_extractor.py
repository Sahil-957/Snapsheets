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


def _clean_text_field(value: str | None) -> str | None:
    cleaned = _clean(value or "")
    if not cleaned:
        return None
    cleaned = re.sub(r"\s*[|.,;:]+\s*$", "", cleaned).strip()
    if cleaned.lower().startswith("select weave"):
        return None
    if cleaned.lower() in {"select", "weave"}:
        return None
    return cleaned or None


def _extract_date(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", value)
    if match:
        return match.group(0).replace("-", "/")
    compact = re.search(r"\b(\d{2})(\d{2})(\d{4})\b", value.replace("/", "").replace("-", ""))
    if compact:
        return f"{compact.group(1)}/{compact.group(2)}/{compact.group(3)}"
    return _clean_text_field(value)


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


def _extract_date_crop(
    image: np.ndarray,
    region: tuple[float, float, float, float],
) -> tuple[str | None, float]:
    text, confidence = _extract_crop_text(
        image,
        region,
        config="--psm 7 -c tessedit_char_whitelist=0123456789/",
        scale=6,
        threshold=True,
    )
    return _extract_date(text), confidence


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
        "date": ((0.074, 0.100, 0.168, 0.132), "date"),
        "agent": ((0.211, 0.083, 0.290, 0.118), "text"),
        "customer": ((0.409, 0.083, 0.520, 0.118), "text"),
        "sourcing_executive": ((0.621, 0.082, 0.711, 0.118), "text"),
        "weave": ((0.892, 0.082, 0.968, 0.118), "text"),
        "quality": ((0.054, 0.150, 0.113, 0.212), "multiline"),
        "shafts": ((0.222, 0.169, 0.295, 0.198), "text"),
        "marketing_executive": ((0.410, 0.169, 0.522, 0.198), "text"),
        "buyer_reference_no": ((0.662, 0.168, 0.770, 0.198), "text"),
        "design_no": ((0.884, 0.169, 0.970, 0.198), "text"),
    }
    for field_name, (region, mode) in top_fields.items():
        if mode == "date":
            value, confidence = _extract_date_crop(image, region)
        elif mode == "multiline":
            value, confidence = _extract_crop_text(image, region, config="--psm 6", scale=6, threshold=False)
        else:
            value, confidence = _extract_crop_text(image, region, config="--psm 7", scale=6)
            value = _clean_text_field(value)
        setattr(row, field_name, value if field_name != "quality" else _clean_text_field(value))
        confidences.append(confidence)

    row.is_warp_butta = _extract_checkbox(image, (0.12, 0.212, 0.135, 0.235))
    row.is_weft_butta = _extract_checkbox(image, (0.275, 0.212, 0.29, 0.235))
    row.is_warp2_sizing_count = _extract_checkbox(image, (0.43, 0.212, 0.445, 0.235))
    row.is_seersucker = _extract_checkbox(image, (0.595, 0.212, 0.61, 0.235))

    yarn_columns = {
        "count": (0.217, 0.0, 0.255, 1.0),
        "rate_per_kg": (0.286, 0.0, 0.350, 1.0),
        "rate_incl_gst": (0.384, 0.0, 0.454, 1.0),
        "gst": (0.490, 0.0, 0.532, 1.0),
        "content": (0.562, 0.0, 0.605, 1.0),
        "yarn_type": (0.620, 0.0, 0.676, 1.0),
        "mill": (0.736, 0.0, 0.772, 1.0),
        "epi_on_loom": (0.796, 0.0, 0.848, 1.0),
        "ppi": (0.904, 0.0, 0.946, 1.0),
    }
    warp_regions = [
        (0.024, 0.371, 0.568, 0.406),
        (0.024, 0.406, 0.568, 0.441),
        (0.024, 0.441, 0.568, 0.476),
    ]
    weft_region = (0.024, 0.476, 0.568, 0.511)

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
        "grey_width": (0.693, 0.316, 0.774, 0.352),
        "epi_on_table": (0.692, 0.353, 0.775, 0.388),
        "meters_per_120_yards": (0.694, 0.415, 0.777, 0.450),
        "total_ends": (0.693, 0.451, 0.782, 0.486),
        "epi_difference": (0.904, 0.317, 0.962, 0.352),
        "reed_space": (0.904, 0.353, 0.962, 0.388),
        "warp_crimp_percent": (0.904, 0.415, 0.962, 0.450),
    }
    for field_name, region in right_metric_fields.items():
        value, confidence = _extract_numeric_crop(image, region)
        setattr(row, field_name, value)
        confidences.append(confidence)

    lower_left_fields = {
        "weight_warp1": (0.083, 0.605, 0.127, 0.640),
        "cost_warp1": (0.136, 0.605, 0.183, 0.640),
        "composition_warp1": (0.188, 0.605, 0.237, 0.640),
        "weight_weft1": (0.083, 0.676, 0.127, 0.711),
        "cost_weft1": (0.136, 0.676, 0.183, 0.711),
        "composition_weft1": (0.188, 0.676, 0.237, 0.711),
        "gsm_total_yarn_cost": (0.086, 0.739, 0.126, 0.774),
        "fabric_total_yarn_cost": (0.137, 0.739, 0.188, 0.774),
        "fabric_weight_glm_inc_sizing": (0.086, 0.789, 0.128, 0.824),
    }
    for field_name, region in lower_left_fields.items():
        value, confidence = _extract_numeric_crop(image, region)
        setattr(row, field_name, value)
        confidences.append(confidence)

    particular_regions = {
        "sizing_per_kg": (0.424, 0.546, 0.722, 0.579),
        "weaving_charges": (0.424, 0.581, 0.722, 0.614),
        "freight": (0.424, 0.617, 0.722, 0.650),
        "butta_cutting": (0.424, 0.652, 0.722, 0.685),
        "yarn_wastage": (0.424, 0.688, 0.722, 0.721),
        "value_loss_interest": (0.424, 0.724, 0.722, 0.757),
        "payment_term": (0.424, 0.761, 0.722, 0.794),
        "particulars_total": (0.424, 0.797, 0.722, 0.830),
        "commission_cd": (0.424, 0.835, 0.722, 0.867),
        "remark": (0.424, 0.871, 0.722, 0.903),
        "other_cost_if_any": (0.451, 0.906, 0.735, 0.940),
        "extra_remarks_if_any": (0.451, 0.940, 0.735, 0.973),
    }

    row.sizing_per_kg_rate, row.sizing_per_kg_cost = _extract_particular_row(image, particular_regions["sizing_per_kg"])
    row.weaving_charges_rate, row.weaving_charges_cost = _extract_particular_row(image, particular_regions["weaving_charges"])
    row.freight_rate, row.freight_cost = _extract_particular_row(image, particular_regions["freight"])
    row.butta_cutting_rate, row.butta_cutting_cost = _extract_particular_row(image, particular_regions["butta_cutting"])
    row.yarn_wastage_rate, row.yarn_wastage_cost = _extract_particular_row(image, particular_regions["yarn_wastage"])
    row.value_loss_interest_rate, row.value_loss_interest_cost = _extract_particular_row(image, particular_regions["value_loss_interest"])
    row.commission_cd_rate, row.commission_cd_cost = _extract_particular_row(image, particular_regions["commission_cd"])

    row.payment_term, conf = _extract_crop_text(image, particular_regions["payment_term"], config="--psm 7", scale=6)
    confidences.append(conf)
    row.payment_term = _clean_text_field(row.payment_term)
    row.particulars_total_cost, conf = _extract_numeric_crop(image, particular_regions["particulars_total"], scale=6)
    confidences.append(conf)
    row.remark, conf = _extract_crop_text(image, particular_regions["remark"], config="--psm 7", scale=6)
    row.remark = _clean_text_field(row.remark)
    confidences.append(conf)
    row.other_cost_if_any_rate, row.other_cost_if_any_remarks = (
        _extract_particular_row(image, particular_regions["other_cost_if_any"])
    )
    row.extra_remarks_if_any, conf = _extract_crop_text(
        image,
        particular_regions["extra_remarks_if_any"],
        config="--psm 6",
        scale=6,
    )
    row.extra_remarks_if_any = _clean_text_field(row.extra_remarks_if_any)
    confidences.append(conf)

    right_cost_fields = {
        "total_price": (0.890, 0.548, 0.949, 0.580),
        "target_price": (0.890, 0.582, 0.949, 0.614),
        "weaving_charge_as_per_tp": (0.890, 0.618, 0.949, 0.649),
        "order_quantity": (0.890, 0.653, 0.962, 0.685),
        "yarn_requirement_warp1": (0.890, 0.688, 0.949, 0.719),
        "yarn_requirement_weft1": (0.890, 0.758, 0.949, 0.789),
        "yarn_requirement_total": (0.890, 0.828, 0.949, 0.860),
        "cover_factor": (0.890, 0.899, 0.949, 0.931),
    }
    for field_name, region in right_cost_fields.items():
        value, confidence = _extract_numeric_crop(image, region)
        setattr(row, field_name, value)
        confidences.append(confidence)

    if row.quality:
        row.quality = row.quality.replace("lity", "").strip()
        row.quality = _clean_text_field(row.quality)

    row.agent = _clean_text_field(row.agent)
    row.customer = _clean_text_field(row.customer)
    row.sourcing_executive = _clean_text_field(row.sourcing_executive)
    row.weave = _clean_text_field(row.weave)
    row.marketing_executive = _clean_text_field(row.marketing_executive)
    row.buyer_reference_no = _clean_text_field(row.buyer_reference_no)
    row.design_no = _clean_text_field(row.design_no)

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
