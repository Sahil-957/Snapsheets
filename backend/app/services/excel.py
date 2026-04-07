from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.schemas import ExtractedRow


def write_excel(rows: list[ExtractedRow], output_path: Path) -> Path:
    frame = pd.DataFrame([row.model_dump() for row in rows])
    if not frame.empty:
        frame.sort_values(by=["status", "image_name"], inplace=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name="Extracted Data")
    return output_path
