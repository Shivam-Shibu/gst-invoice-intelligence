from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


def export_dataframe(df: pd.DataFrame, output_dir: Path, stem: str, file_type: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"{stem}_{timestamp}.{file_type}"

    if file_type == "csv":
        df.to_csv(path, index=False)
    elif file_type == "xlsx":
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Invoices")
            worksheet = writer.sheets["Invoices"]
            for column_cells in worksheet.columns:
                max_length = max(len(str(cell.value or "")) for cell in column_cells)
                worksheet.column_dimensions[column_cells[0].column_letter].width = min(max(max_length + 2, 12), 48)
    else:
        raise ValueError(f"Unsupported export type: {file_type}")

    return path


def to_download_bytes(path: Path) -> bytes:
    return path.read_bytes()
