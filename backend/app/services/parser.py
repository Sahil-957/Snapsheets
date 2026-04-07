from __future__ import annotations

import re
from pathlib import Path

from app.schemas import ExtractedRow


FIELD_PATTERNS: dict[str, list[str]] = {
    "date": [r"DATE[:\s\-]*([A-Z0-9\/\-. ]{6,20})"],
    "agent": [r"AGENT[:\s\-]*([A-Z0-9&.,\- ]{2,80})"],
    "customer": [r"CUSTOMER[:\s\-]*([A-Z0-9&.,\- ]{2,80})"],
    "quality": [r"QUALITY[:\s\-]*([A-Z0-9/\- ]{2,80})"],
    "warp_counts": [r"WARP(?: COUNT)?S?[:\s\-]*([A-Z0-9/.\- xX]+)"],
    "weft_counts": [r"WEFT(?: COUNT)?S?[:\s\-]*([A-Z0-9/.\- xX]+)"],
    "total_price": [r"TOTAL PRICE[:\s\-]*([0-9,.]+)"],
    "target_price": [r"TARGET PRICE[:\s\-]*([0-9,.]+)"],
    "order_quantity": [r"ORDER QUANTITY[:\s\-]*([A-Z0-9,. ]+)"],
    "yarn_requirement": [r"YARN REQUIREMENT[:\s\-]*([A-Z0-9,. ]+)"],
    "composition": [r"COMPOSITION[:\s\-]*([A-Z0-9/% ,.\-]+)"],
    "gsm_fabric_weight": [r"(?:GSM|FABRIC WEIGHT)[:\s\-]*([A-Z0-9,. ]+)"],
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
        "gsm_fabric_weight": ["FABRIC WEIGHT", "(GLM) INC. SIZING"],
    }

    for field_name, labels in line_map.items():
        value = _extract_from_lines(lines, labels) or _extract(FIELD_PATTERNS.get(field_name, []), normalized)
        setattr(row, field_name, value)

    quality = row.quality or ""
    count_pairs = re.findall(r"(\d+\*\d+|\d+/\d+)", quality)
    if count_pairs:
        row.warp_counts = count_pairs[0]
        if len(count_pairs) > 1:
            row.weft_counts = count_pairs[1]

    yarn_matches = re.findall(r"(WARP\d*|WEFT\d*|TOTAL)\s*[:\-]?\s*([0-9]+(?:\.\d+)?)", normalized)
    if yarn_matches:
        row.yarn_requirement = ", ".join(f"{label}: {value}" for label, value in yarn_matches)

    yarn_section_match = re.search(
        r"YARN REQUIREMENT\s*(.*?)\s*COVER FACTOR",
        normalized,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if yarn_section_match:
        yarn_section = yarn_section_match.group(1)
        yarn_matches = re.findall(r"(WARP\d*|WEFT\d*|TOTAL)\s*[:\-]?\s*([0-9]+(?:\.\d+)?)", yarn_section)
        if yarn_matches:
            row.yarn_requirement = ", ".join(f"{label}: {value}" for label, value in yarn_matches)

    if not row.composition:
        composition_tokens = [token for token in ["COTTON", "LINEN", "VISCOSE", "PC", "BCI"] if token in quality.upper()]
        if composition_tokens:
            row.composition = ", ".join(composition_tokens)

    if not row.weft_counts:
        row.weft_counts = _extract(FIELD_PATTERNS["weft_counts"], normalized)
    if not row.warp_counts:
        row.warp_counts = _extract(FIELD_PATTERNS["warp_counts"], normalized)

    low_confidence_fields: list[str] = [
        field_name for field_name in FIELD_PATTERNS if not getattr(row, field_name, None)
    ]

    row.low_confidence_fields = low_confidence_fields
    return row


def error_row(image_path: Path, message: str) -> ExtractedRow:
    return ExtractedRow(
        image_name=image_path.name,
        status="ERROR",
        error_message=message,
        low_confidence_fields=list(FIELD_PATTERNS.keys()),
    )
