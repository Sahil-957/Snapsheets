from __future__ import annotations

import re
from pathlib import Path

from app.schemas import ExtractedRow


FIELD_PATTERNS: dict[str, list[str]] = {
    "date": [r"DATE[:\s\-]*([A-Z0-9\/\-. ]{6,20})"],
    "agent": [r"AGENT[:\s\-]*([A-Z0-9&.,\- ]{2,80})"],
    "customer": [r"CUSTOMER[:\s\-]*([A-Z0-9&.,\- ]{2,80})"],
    "quality": [r"QUALITY[:\s\-]*([A-Z0-9/\- ]{2,80})"],
    "warp_count": [r"WARP(?: COUNT)?S?[:\s\-]*([A-Z0-9/.\- xX]+)"],
    "weft_count": [r"WEFT(?: COUNT)?S?[:\s\-]*([A-Z0-9/.\- xX]+)"],
    "total_price": [r"TOTAL PRICE[:\s\-]*([0-9,.]+)"],
    "target_price": [r"TARGET PRICE[:\s\-]*([0-9,.]+)"],
    "order_quantity": [r"ORDER QUANTITY[:\s\-]*([A-Z0-9,. ]+)"],
    "yarn_requirement_total": [r"TOTAL[:\s\-]*([0-9,.]+)"],
    "fabric_weight_glm_inc_sizing": [r"(?:FABRIC WEIGHT|\(GLM\) INC\. SIZING)[:\s\-]*([A-Z0-9,. ]+)"],
    "grey_width": [r"GREY WIDTH[:\s\-]*([0-9,.]+)"],
    "epi_on_table": [r"EPI ON TABLE[:\s\-]*([0-9,.]+)"],
    "meters_per_120_yards": [r"METERS PER 120(?: YARDS)?[:\s\-]*([0-9,.]+)"],
    "total_ends": [r"TOTAL ENDS[:\s\-]*([0-9,.]+)"],
    "epi_difference": [r"EPI DIFFERENCE[:\s\-]*([0-9,.]+)"],
    "reed_space": [r"REED SPACE[:\s\-]*([0-9,.]+)"],
    "warp_crimp_percent": [r"WARP CRIMP %?[:\s\-]*([0-9,.]+)"],
    "weaving_charge_as_per_tp": [r"WEAVING CHARGE AS PER TP[:\s\-]*([0-9,.]+)"],
    "cover_factor": [r"COVER FACTOR[:\s\-]*([0-9,.]+)"],
    "payment_term": [r"PAYMENT TERM[:\s\-]*([A-Z0-9 .]+)"],
    "particulars_total_cost": [r"\bTOTAL[:\s\-]*([0-9,.]+)"],
    "commission_cd_rate": [r"COMMISSION\s*&\s*CD%[:\s\-]*([0-9,.]+)"],
}


def _normalize(text: str) -> str:
    cleaned = text.replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned.upper()


def _clean_value(value: str) -> str | None:
    cleaned = re.sub(r"\s+", " ", value).strip(" :-|")
    return cleaned or None


def _normalize_numeric(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
    return match.group(0) if match else _clean_value(value)


KNOWN_LABELS = {
    "DATE",
    "AGENT",
    "CUSTOMER",
    "QUALITY",
    "SHAFTS",
    "MARKETING EXECUTIVE",
    "SOURCING EXECUTIVE",
    "BUYER REFERENCE NO.",
    "DESIGN NO.",
    "TOTAL PRICE",
    "TOTAL PRICE*",
    "TARGET PRICE",
    "ORDER QUANTITY",
    "YARN REQUIREMENT",
    "COVER FACTOR",
    "FABRIC WEIGHT",
    "(GLM) INC. SIZING",
}


def _next_value(lines: list[str], start_index: int) -> str | None:
    for line in lines[start_index + 1:]:
        candidate = _clean_value(line)
        if not candidate:
            continue
        if candidate.upper() in KNOWN_LABELS:
            continue
        return candidate
    return None


def _extract_from_lines(lines: list[str], labels: list[str]) -> str | None:
    for index, line in enumerate(lines):
        upper_line = line.upper()
        for label in labels:
            if upper_line == label or upper_line.startswith(f"{label}:"):
                same_line = line[len(label):].strip(" :-")
                return _clean_value(same_line) or _next_value(lines, index)
            if label in upper_line:
                match = re.search(rf"{re.escape(label)}[:\s]*([A-Z0-9/%.,()\"'&+\- ]+)", line, flags=re.IGNORECASE)
                if match:
                    return _clean_value(match.group(1))
    return None


def _extract(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(" :-")
    return None


def _extract_label_value(lines: list[str], labels: list[str], *, numeric: bool = False) -> str | None:
    value = _extract_from_lines(lines, labels)
    return _normalize_numeric(value) if numeric else value


def _find_section(lines: list[str], start_labels: list[str], stop_labels: list[str]) -> list[str]:
    start_index: int | None = None
    for index, line in enumerate(lines):
        upper = line.upper()
        if any(label in upper for label in start_labels):
            start_index = index
            break
    if start_index is None:
        return []

    section: list[str] = []
    for line in lines[start_index:]:
        upper = line.upper()
        if section and any(label in upper for label in stop_labels):
            break
        section.append(line)
    return section


def _parse_count_rows(lines: list[str]) -> dict[str, list[str]]:
    parsed: dict[str, list[str]] = {}
    for line in lines:
        upper = line.upper()
        if "COUNT" not in upper:
            continue
        if not ("WARP" in upper or "WEFT" in upper):
            continue

        kind = "weft" if "WEFT" in upper else "warp"
        numerics = re.findall(r"-?\d+(?:\.\d+)?", line.replace(",", ""))
        if len(numerics) < 4:
            continue
        parsed.setdefault(f"{kind}_count", []).append(numerics[0])
        parsed.setdefault(f"{kind}_rate_per_kg", []).append(numerics[1])
        parsed.setdefault(f"{kind}_rate_incl_gst", []).append(numerics[2])
        parsed.setdefault(f"{kind}_gst", []).append(numerics[3])
        if len(numerics) >= 5:
            if kind == "weft":
                parsed.setdefault("weft_ppi", []).append(numerics[-1])
            else:
                parsed.setdefault("warp_epi_on_loom", []).append(numerics[-1])

        text_after_gst = re.split(r"-?\d+(?:\.\d+)?", line, maxsplit=4)
        if len(text_after_gst) >= 5:
            tail = _clean_value(text_after_gst[-1] or "")
            if tail:
                tokens = tail.split()
                if tokens:
                    parsed.setdefault(f"{kind}_content", []).append(tokens[0])
                if len(tokens) >= 2:
                    parsed.setdefault(f"{kind}_yarn_type", []).append(tokens[1])
                if len(tokens) >= 3:
                    parsed.setdefault(f"{kind}_mill", []).append(" ".join(tokens[2:]))
    return parsed


def _parse_weight_cost_rows(lines: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in lines:
        upper = line.upper()
        label_map = {
            "WARP1": ("weight_warp1", "cost_warp1", "composition_warp1"),
            "WARP2": (None, None, None),
            "WARP3": (None, None, None),
            "WEFT1": ("weight_weft1", "cost_weft1", "composition_weft1"),
        }
        matched_label = next((label for label in label_map if upper.startswith(label)), None)
        if not matched_label:
            continue
        numerics = re.findall(r"-?\d+(?:\.\d+)?", line.replace(",", ""))
        fields = label_map[matched_label]
        if len(numerics) >= 3:
            if fields[0]:
                parsed[fields[0]] = numerics[0]
            if fields[1]:
                parsed[fields[1]] = numerics[1]
            if fields[2]:
                parsed[fields[2]] = numerics[2]
    return parsed


def _parse_particulars(lines: list[str]) -> dict[str, str]:
    mapping = {
        "SIZING PER KG": ("sizing_per_kg_rate", "sizing_per_kg_cost"),
        "WEAVING CHARGES": ("weaving_charges_rate", "weaving_charges_cost"),
        "FREIGHT PER KG": ("freight_rate", "freight_cost"),
        "BUTTA CUTTING": ("butta_cutting_rate", "butta_cutting_cost"),
        "YARN WASTAGE": ("yarn_wastage_rate", "yarn_wastage_cost"),
        "VALUE LOSS": ("value_loss_interest_rate", "value_loss_interest_cost"),
        "COMMISSION": ("commission_cd_rate", "commission_cd_cost"),
    }
    parsed: dict[str, str] = {}
    for line in lines:
        upper = line.upper()
        for label, fields in mapping.items():
            if label not in upper:
                continue
            numerics = re.findall(r"-?\d+(?:\.\d+)?", line.replace(",", ""))
            if numerics:
                parsed[fields[0]] = numerics[0]
            if len(numerics) >= 2:
                parsed[fields[1]] = numerics[1]
        if "PAYMENT TERM" in upper:
            value = re.sub(r"PAYMENT TERM[:\s\-]*", "", line, flags=re.IGNORECASE).strip()
            cleaned = _clean_value(value)
            if cleaned:
                parsed["payment_term"] = cleaned
        if upper.startswith("TOTAL") or " TOTAL " in f" {upper} ":
            numerics = re.findall(r"-?\d+(?:\.\d+)?", line.replace(",", ""))
            if numerics:
                parsed["particulars_total_cost"] = numerics[-1]
        if upper.startswith("REMARK"):
            value = re.sub(r"REMARK[:\s\-]*", "", line, flags=re.IGNORECASE).strip()
            cleaned = _clean_value(value)
            if cleaned:
                parsed["remark"] = cleaned
        if "OTHER COST IF ANY" in upper:
            numerics = re.findall(r"-?\d+(?:\.\d+)?", line.replace(",", ""))
            if numerics:
                parsed["other_cost_if_any_rate"] = numerics[0]
        if "EXTRA REMARKS IF ANY" in upper:
            value = re.sub(r"EXTRA REMARKS IF ANY[:\s\-]*", "", line, flags=re.IGNORECASE).strip()
            cleaned = _clean_value(value)
            if cleaned:
                parsed["extra_remarks_if_any"] = cleaned
    return parsed


def parse_structured_text(image_name: str, text: str, confidence: float, engine: str) -> ExtractedRow:
    normalized = _normalize(text)
    raw_lines = [line.strip() for line in text.replace("\r", "\n").split("\n")]
    lines = [line for line in raw_lines if line.strip()]
    row = ExtractedRow(image_name=image_name, source_file=image_name, ocr_confidence=confidence, ocr_engine=engine)

    line_map = {
        "date": ["DATE"],
        "agent": ["AGENT"],
        "customer": ["CUSTOMER"],
        "quality": ["QUALITY"],
        "total_price": ["TOTAL PRICE", "TOTAL PRICE*"],
        "target_price": ["TARGET PRICE"],
        "order_quantity": ["ORDER QUANTITY"],
        "fabric_weight_glm_inc_sizing": ["FABRIC WEIGHT", "(GLM) INC. SIZING"],
    }

    for field_name, labels in line_map.items():
        value = _extract_from_lines(lines, labels) or _extract(FIELD_PATTERNS.get(field_name, []), normalized)
        setattr(row, field_name, value)

    numeric_line_map = {
        "grey_width": ["GREY WIDTH"],
        "epi_on_table": ["EPI ON TABLE"],
        "meters_per_120_yards": ["METERS PER 120", "METERS PER 120 YARDS"],
        "total_ends": ["TOTAL ENDS"],
        "epi_difference": ["EPI DIFFERENCE"],
        "reed_space": ["REED SPACE"],
        "warp_crimp_percent": ["WARP CRIMP"],
        "weaving_charge_as_per_tp": ["WEAVING CHARGE AS PER TP"],
        "cover_factor": ["COVER FACTOR"],
    }
    for field_name, labels in numeric_line_map.items():
        value = _extract_label_value(lines, labels, numeric=True) or _extract(FIELD_PATTERNS.get(field_name, []), normalized)
        setattr(row, field_name, value)

    quality = row.quality or ""
    count_pairs = re.findall(r"(\d+\*\d+|\d+/\d+)", quality)
    if count_pairs:
        row.warp_count = count_pairs[0]
        if len(count_pairs) > 1:
            row.weft_count = count_pairs[1]

    yarn_matches = re.findall(r"(WARP\d*|WEFT\d*|TOTAL)\s*[:\-]?\s*([0-9]+(?:\.\d+)?)", normalized)
    if yarn_matches:
        for label, value in yarn_matches:
            upper = label.upper()
            if upper.startswith("WARP1"):
                row.yarn_requirement_warp1 = value
            elif upper.startswith("WEFT1") or upper == "WEFT":
                row.yarn_requirement_weft1 = value
            elif upper == "TOTAL":
                row.yarn_requirement_total = value

    yarn_section_match = re.search(
        r"YARN REQUIREMENT\s*(.*?)\s*COVER FACTOR",
        normalized,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if yarn_section_match:
        yarn_section = yarn_section_match.group(1)
        yarn_matches = re.findall(r"(WARP\d*|WEFT\d*|TOTAL)\s*[:\-]?\s*([0-9]+(?:\.\d+)?)", yarn_section)
        if yarn_matches:
            for label, value in yarn_matches:
                upper = label.upper()
                if upper.startswith("WARP1"):
                    row.yarn_requirement_warp1 = value
                elif upper.startswith("WEFT1") or upper == "WEFT":
                    row.yarn_requirement_weft1 = value
                elif upper == "TOTAL":
                    row.yarn_requirement_total = value

    count_rows = _parse_count_rows(lines)
    for key, values in count_rows.items():
        current = getattr(row, key, None)
        if current in (None, "", []):
            setattr(row, key, " | ".join(values))

    weight_section = _find_section(lines, ["WEIGHT & COST", "WEIGHT"], ["PARTICULARS", "TOTAL PRICE"])
    for key, value in _parse_weight_cost_rows(weight_section or lines).items():
        if getattr(row, key, None) in (None, "", []):
            setattr(row, key, value)

    particulars_section = _find_section(lines, ["PARTICULARS", "SIZING PER KG"], ["TOTAL PRICE", "COVER FACTOR"])
    for key, value in _parse_particulars(particulars_section or lines).items():
        if getattr(row, key, None) in (None, "", []):
            setattr(row, key, value)

    if not row.remark:
        composition_tokens = [token for token in ["COTTON", "LINEN", "VISCOSE", "PC", "BCI"] if token in quality.upper()]
        if composition_tokens:
            row.remark = ", ".join(composition_tokens)

    if not row.weft_count:
        row.weft_count = _extract(FIELD_PATTERNS["weft_count"], normalized)
    if not row.warp_count:
        row.warp_count = _extract(FIELD_PATTERNS["warp_count"], normalized)

    low_confidence_fields: list[str] = [
        field_name for field_name in FIELD_PATTERNS if not getattr(row, field_name, None)
    ]

    row.low_confidence_fields = low_confidence_fields
    return row


def error_row(image_path: Path, message: str) -> ExtractedRow:
    return ExtractedRow(
        image_name=image_path.name,
        source_file=image_path.name,
        status="ERROR",
        error_message=message,
        low_confidence_fields=list(FIELD_PATTERNS.keys()),
    )
