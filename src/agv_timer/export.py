"""CSV export for the visible measurement rows."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from .measurement import MeasurementModel, format_seconds, format_timestamp


CSV_HEADER = ("No.", "时间戳", "节拍(s)", "偏差(s)")


def write_csv(path: str | Path, model: MeasurementModel) -> None:
    destination = Path(path)
    with destination.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(CSV_HEADER)
        for record in model.records:
            interval = Decimal(record.interval_ms) / Decimal(1000)
            writer.writerow(
                (
                    f"{record.number:02d}",
                    format_timestamp(record.timestamp_ms),
                    format_seconds(interval),
                    format_seconds(model.deviation_seconds(record), signed=True),
                )
            )
