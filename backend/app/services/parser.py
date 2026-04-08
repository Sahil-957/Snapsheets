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
}


def _normalize(text: str) -> str:
    cleaned = text.replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned.upper()


def _clean_value(value: str) -> str | None:
    cleaned = re.sub(r"\s+", " ", value).strip(" :-|")
    return cleaned or None


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


def parse_structured_text(image_name: str, text: str, confidence: float, engine: str) -> ExtractedRow:
    normalized = _normalize(text)
    raw_lines = [line.strip() for line in text.replace("\r", "\n").split("\n")]
    lines = [line for line in raw_lines if line.strip()]
    row = ExtractedRow(image_name=image_name, ocr_confidence=confidence, ocr_engine=engine)

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
