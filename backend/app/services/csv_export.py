"""CSV export helpers for streaming tenant data."""

import csv
import io
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def _format_value(v: Any) -> str:
    """Format a value for CSV output."""
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    return str(v)


def rows_to_csv_bytes(headers: list[str], rows: Sequence[Sequence[Any]]) -> bytes:
    """Convert header + rows into UTF-8 CSV bytes with BOM for Excel compatibility."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_format_value(v) for v in row])
    # UTF-8 BOM so Excel auto-detects encoding (important for Arabic names)
    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")
