from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.schemas import ExtractedRow


def _clean(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip(" |[](){}:_-")
    cleaned = re.sub(r"\s+([.,:/%])", r"\1", cleaned)
    cleaned = re.sub(r"([(/])\s+", r"\1", cleaned)
    if cleaned.upper() in {
        "SELECT",
        "SELECT WEAVE",
        "+ SELECT",
        "EE",
        "OOO",
        "-",
        "—",
    }:
        return None
    return cleaned or None


def _normalize_numeric(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
    return match.group(0) if match else _clean(value)


def _numbers(value: str | None) -> list[str]:
    if not value:
        return []
    return re.findall(r"-?\d+(?:\.\d+)?", value.replace(",", ""))


def _numbers_in_region(
    words: list[dict[str, Any]],
    region: tuple[float, float, float, float],
    width: int,
    height: int,
) -> list[str]:
    return _numbers(_text_in_region(words, region, width, height))


def _normalize_region(region: tuple[float, float, float, float], width: int, height: int) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = region
    return width * x1, height * y1, width * x2, height * y2


def _words_in_region(
    words: list[dict[str, Any]],
    region: tuple[float, float, float, float],
    width: int,
    height: int,
) -> list[dict[str, Any]]:
    x1, y1, x2, y2 = _normalize_region(region, width, height)
    matched = [
        word
        for word in words
        if x1 <= float(word["cx"]) <= x2 and y1 <= float(word["cy"]) <= y2
    ]
    return sorted(matched, key=lambda word: (round(float(word["cy"]) / 6), float(word["left"])))


def _text_in_region(
    words: list[dict[str, Any]],
    region: tuple[float, float, float, float],
    width: int,
    height: int,
) -> str | None:
    matched = _words_in_region(words, region, width, height)
    if not matched:
        return None

    lines: list[list[str]] = []
    line_positions: list[float] = []
    for word in matched:
        cy = float(word["cy"])
        token = str(word["text"])
        placed = False
        for index, line_y in enumerate(line_positions):
            if abs(cy - line_y) <= 10:
                lines[index].append(token)
                line_positions[index] = (line_y + cy) / 2.0
                placed = True
                break
        if not placed:
            lines.append([token])
            line_positions.append(cy)

    return _clean(" | ".join(" ".join(line) for line in lines))


def _last_number_in_region(words: list[dict[str, Any]], region: tuple[float, float, float, float], width: int, height: int) -> str | None:
    text = _text_in_region(words, region, width, height)
    nums = _numbers(text)
    return nums[-1] if nums else None


def _first_number_in_region(words: list[dict[str, Any]], region: tuple[float, float, float, float], width: int, height: int) -> str | None:
    text = _text_in_region(words, region, width, height)
    nums = _numbers(text)
    return nums[0] if nums else None


def _checkbox(image: np.ndarray, region: tuple[float, float, float, float]) -> bool:
    height, width = image.shape[:2]
    x1, y1, x2, y2 = _normalize_region(region, width, height)
    crop = image[int(y1): int(y2), int(x1): int(x2)]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
    fill_ratio = float(np.count_nonzero(binary)) / float(binary.size or 1)
    return fill_ratio > 0.12


def _join(values: list[str | None]) -> str | None:
    cleaned = [_clean(value) for value in values if _clean(value)]
    return " | ".join(cleaned) if cleaned else None


def _join_numeric(values: list[str | None]) -> str | None:
    nums: list[str] = []
    for value in values:
        if not value:
            continue
        extracted = _numbers(value)
        if extracted:
            nums.append(extracted[-1])
    return " | ".join(nums) if nums else None


def _cell(
    panel: tuple[float, float, float, float],
    col: tuple[float, float],
    row: tuple[float, float],
) -> tuple[float, float, float, float]:
    px1, py1, px2, py2 = panel
    panel_w = px2 - px1
    panel_h = py2 - py1
    return (
        px1 + panel_w * col[0],
        py1 + panel_h * row[0],
        px1 + panel_w * col[1],
        py1 + panel_h * row[1],
    )


def extract_vision_layout_fields(image_path: Path, words: list[dict[str, Any]]) -> ExtractedRow:
    image = cv2.imread(str(image_path))
    if image is None:
        return ExtractedRow(image_name=image_path.name, source_file=image_path.name, status="ERROR", error_message="Unable to load image.")

    height, width = image.shape[:2]
    row = ExtractedRow(
        image_name=image_path.name,
        source_file=image_path.name,
        ocr_engine="google-vision-layout",
    )

    text_fields = {
        "date": (0.070, 0.080, 0.170, 0.140),
        "agent": (0.205, 0.070, 0.300, 0.130),
        "customer": (0.400, 0.070, 0.535, 0.130),
        "sourcing_executive": (0.620, 0.070, 0.715, 0.130),
        "weave": (0.905, 0.070, 0.970, 0.130),
        "quality": (0.045, 0.145, 0.180, 0.235),
        "shafts": (0.210, 0.145, 0.315, 0.210),
        "marketing_executive": (0.405, 0.145, 0.545, 0.210),
        "buyer_reference_no": (0.640, 0.145, 0.790, 0.210),
        "design_no": (0.860, 0.145, 0.980, 0.210),
    }
    for field_name, region in text_fields.items():
        setattr(row, field_name, _text_in_region(words, region, width, height))

    if row.sourcing_executive and len(row.sourcing_executive.strip()) <= 1:
        row.sourcing_executive = None
    if row.weave and "WEAVE" in row.weave.upper():
        row.weave = None
    if row.design_no and row.design_no.lower() in {"ee", "ooo"}:
        row.design_no = None

    row.is_warp_butta = _checkbox(image, (0.12, 0.212, 0.135, 0.235))
    row.is_weft_butta = _checkbox(image, (0.275, 0.212, 0.29, 0.235))
    row.is_warp2_sizing_count = _checkbox(image, (0.43, 0.212, 0.445, 0.235))
    row.is_seersucker = _checkbox(image, (0.595, 0.212, 0.61, 0.235))

    yarn_panel = (0.024, 0.345, 0.568, 0.512)
    yarn_columns = {
        "count": (0.228, 0.262),
        "rate_per_kg": (0.297, 0.365),
        "rate_incl_gst": (0.386, 0.458),
        "gst": (0.497, 0.539),
        "content": (0.568, 0.614),
        "yarn_type": (0.637, 0.690),
        "mill": (0.737, 0.781),
        "epi_on_loom": (0.803, 0.853),
        "ppi": (0.878, 0.930),
    }
    yarn_rows = {
        "warp1": (0.290, 0.435),
        "warp2": (0.438, 0.585),
        "warp3": (0.586, 0.732),
        "weft1": (0.732, 0.878),
    }

    warp_values: dict[str, list[str | None]] = {key: [] for key in yarn_columns}
    for row_name in ("warp1", "warp2", "warp3"):
        row_range = yarn_rows[row_name]
        row_box = {}
        for key, col_region in yarn_columns.items():
            absolute_region = _cell(yarn_panel, col_region, row_range)
            if key in {"count", "rate_per_kg", "rate_incl_gst", "gst", "epi_on_loom", "ppi"}:
                nums = _numbers_in_region(words, absolute_region, width, height)
                value = nums[-1] if nums else None
            else:
                value = _text_in_region(words, absolute_region, width, height)
            row_box[key] = value
        if any(row_box.get(key) for key in ("count", "rate_per_kg", "rate_incl_gst")):
            for key, value in row_box.items():
                warp_values[key].append(_clean(value) if key not in {"count", "rate_per_kg", "rate_incl_gst", "gst", "epi_on_loom", "ppi"} else value)

    row.warp_count = _join_numeric(warp_values["count"])
    row.warp_rate_per_kg = _join_numeric(warp_values["rate_per_kg"])
    row.warp_rate_incl_gst = _join_numeric(warp_values["rate_incl_gst"])
    row.warp_gst = _join_numeric(warp_values["gst"])
    row.warp_content = _join(warp_values["content"])
    row.warp_yarn_type = _join(warp_values["yarn_type"])
    row.warp_mill = _join(warp_values["mill"])
    row.warp_epi_on_loom = _join_numeric(warp_values["epi_on_loom"])

    weft_box = {}
    for key, col_region in yarn_columns.items():
        absolute_region = _cell(yarn_panel, col_region, yarn_rows["weft1"])
        if key in {"count", "rate_per_kg", "rate_incl_gst", "gst", "epi_on_loom", "ppi"}:
            nums = _numbers_in_region(words, absolute_region, width, height)
            value = nums[-1] if nums else None
        else:
            value = _text_in_region(words, absolute_region, width, height)
        weft_box[key] = value

    row.weft_count = _normalize_numeric(weft_box.get("count"))
    row.weft_rate_per_kg = _normalize_numeric(weft_box.get("rate_per_kg"))
    row.weft_rate_incl_gst = _normalize_numeric(weft_box.get("rate_incl_gst"))
    row.weft_gst = _normalize_numeric(weft_box.get("gst"))
    row.weft_content = _clean(weft_box.get("content"))
    row.weft_yarn_type = _clean(weft_box.get("yarn_type"))
    row.weft_mill = _clean(weft_box.get("mill"))
    row.weft_ppi = _normalize_numeric(weft_box.get("ppi"))

    metrics_fields = {
        "grey_width": (0.692, 0.352, 0.784, 0.387),
        "epi_on_table": (0.692, 0.386, 0.784, 0.422),
        "meters_per_120_yards": (0.692, 0.420, 0.784, 0.456),
        "total_ends": (0.692, 0.456, 0.784, 0.494),
        "epi_difference": (0.897, 0.318, 0.970, 0.352),
        "reed_space": (0.897, 0.355, 0.970, 0.389),
        "warp_crimp_percent": (0.897, 0.420, 0.970, 0.456),
    }
    for field_name, region in metrics_fields.items():
        setattr(row, field_name, _last_number_in_region(words, region, width, height))

    weight_panel = (0.024, 0.593, 0.246, 0.828)
    weight_cols = {
        "weight": (0.295, 0.466),
        "cost": (0.534, 0.703),
        "composition": (0.760, 0.972),
    }
    weight_rows = {
        "warp1": (0.167, 0.288),
        "weft1": (0.410, 0.532),
        "gsm_total": (0.548, 0.679),
        "fabric_weight": (0.788, 0.920),
    }
    for key, row_range in weight_rows.items():
        cells = {
            col_name: _numbers_in_region(words, _cell(weight_panel, col_range, row_range), width, height)
            for col_name, col_range in weight_cols.items()
        }
        if key == "warp1":
            row.weight_warp1 = cells["weight"][-1] if cells["weight"] else None
            row.cost_warp1 = cells["cost"][-1] if cells["cost"] else None
            row.composition_warp1 = cells["composition"][-1] if cells["composition"] else None
        elif key == "weft1":
            row.weight_weft1 = cells["weight"][-1] if cells["weight"] else None
            row.cost_weft1 = cells["cost"][-1] if cells["cost"] else None
            row.composition_weft1 = cells["composition"][-1] if cells["composition"] else None
        elif key == "gsm_total":
            row.gsm_total_yarn_cost = cells["weight"][-1] if cells["weight"] else None
            row.fabric_total_yarn_cost = cells["cost"][-1] if cells["cost"] else None
        elif key == "fabric_weight":
            row.fabric_weight_glm_inc_sizing = cells["weight"][-1] if cells["weight"] else None

    particulars_panel = (0.255, 0.533, 0.739, 0.973)
    particulars_cols = {
        "rate": (0.325, 0.490),
        "cost": (0.670, 0.838),
        "remarks": (0.620, 0.990),
        "text": (0.330, 0.980),
    }
    particulars_rows = {
        "sizing_per_kg": (0.109, 0.178),
        "weaving_charges": (0.183, 0.251),
        "freight": (0.258, 0.326),
        "butta_cutting": (0.332, 0.400),
        "yarn_wastage": (0.407, 0.475),
        "value_loss_interest": (0.481, 0.548),
        "payment_term": (0.555, 0.623),
        "particulars_total": (0.629, 0.695),
        "commission_cd": (0.704, 0.773),
        "remark": (0.778, 0.846),
        "other_cost_if_any": (0.894, 0.948),
        "extra_remarks_if_any": (0.953, 0.997),
    }
    mapping = {
        "sizing_per_kg": ("sizing_per_kg_rate", "sizing_per_kg_cost"),
        "weaving_charges": ("weaving_charges_rate", "weaving_charges_cost"),
        "freight": ("freight_rate", "freight_cost"),
        "butta_cutting": ("butta_cutting_rate", "butta_cutting_cost"),
        "yarn_wastage": ("yarn_wastage_rate", "yarn_wastage_cost"),
        "value_loss_interest": ("value_loss_interest_rate", "value_loss_interest_cost"),
        "commission_cd": ("commission_cd_rate", "commission_cd_cost"),
    }
    for key, region in particulars_rows.items():
        rate_nums = _numbers_in_region(words, _cell(particulars_panel, particulars_cols["rate"], region), width, height)
        cost_nums = _numbers_in_region(words, _cell(particulars_panel, particulars_cols["cost"], region), width, height)
        text = _text_in_region(words, _cell(particulars_panel, particulars_cols["text"], region), width, height)
        if key in mapping:
            setattr(row, mapping[key][0], rate_nums[-1] if rate_nums else None)
            setattr(row, mapping[key][1], cost_nums[-1] if cost_nums else None)
        elif key == "payment_term":
            row.payment_term = _clean(text)
        elif key == "particulars_total":
            row.particulars_total_cost = cost_nums[-1] if cost_nums else None
        elif key == "remark":
            remark_text = _text_in_region(words, _cell(particulars_panel, particulars_cols["text"], region), width, height)
            cleaned_remark = _clean(remark_text)
            row.remark = None if cleaned_remark == "Remark" else cleaned_remark
        elif key == "other_cost_if_any":
            row.other_cost_if_any_rate = rate_nums[-1] if rate_nums else None
            row.other_cost_if_any_remarks = _clean(
                _text_in_region(words, _cell(particulars_panel, particulars_cols["remarks"], region), width, height)
            )
        elif key == "extra_remarks_if_any":
            row.extra_remarks_if_any = _clean(text)

    totals_fields = {
        "total_price": (0.878, 0.548, 0.968, 0.580),
        "target_price": (0.878, 0.582, 0.968, 0.614),
        "weaving_charge_as_per_tp": (0.870, 0.618, 0.968, 0.649),
        "order_quantity": (0.884, 0.653, 0.968, 0.685),
        "yarn_requirement_warp1": (0.884, 0.688, 0.968, 0.719),
        "yarn_requirement_weft1": (0.884, 0.722, 0.968, 0.753),
        "yarn_requirement_total": (0.884, 0.792, 0.968, 0.824),
        "cover_factor": (0.884, 0.899, 0.968, 0.931),
    }
    for field_name, region in totals_fields.items():
        setattr(row, field_name, _last_number_in_region(words, region, width, height))

    if row.yarn_requirement_warp1 and row.yarn_requirement_weft1 and not row.yarn_requirement_total:
        try:
            row.yarn_requirement_total = str(
                int(float(row.yarn_requirement_warp1)) + int(float(row.yarn_requirement_weft1))
            )
        except ValueError:
            pass

    if row.warp_content:
        row.warp_content = _join([value for value in (row.warp_content or "").split(" | ") if value and value.upper() not in {"CONTENT", "COT"}])
    if row.weft_content and row.weft_content.upper() in {"RRR", "A", "J", "WEFT"}:
        row.weft_content = None
    if row.warp_mill and row.warp_mill.upper() in {"MILL", "A", "7"}:
        row.warp_mill = None
    if row.weft_mill and row.weft_mill.upper() in {"RRR", "J"}:
        row.weft_mill = None
    if row.epi_difference and not _numbers(row.epi_difference):
        row.epi_difference = None
    if row.weft_count and not _numbers(row.weft_count):
        row.weft_count = None
    if row.fabric_weight_glm_inc_sizing and not _numbers(row.fabric_weight_glm_inc_sizing):
        row.fabric_weight_glm_inc_sizing = None
    if row.remark and row.remark.upper() in {"RATE REMARKS", "REMARK"}:
        row.remark = None
    if row.other_cost_if_any_remarks and row.other_cost_if_any_remarks in {"0", "a"}:
        row.other_cost_if_any_remarks = None

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
    row.status = "REVIEW" if row.low_confidence_fields else "SUCCESS"
    row.ocr_confidence = 95.0
    return row
