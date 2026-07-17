from __future__ import annotations

import re
from typing import Any


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def format_database_size(value: Any) -> str | None:
    """Format Hubitat's database size despite firmware-dependent units.

    Kingpanther's MCP field is named ``databaseSizeKB`` because older Hubitat
    firmware returned kilobytes. Current firmware can return the already-converted
    megabyte value from ``/hub/advanced/databaseSize`` while retaining the same MCP
    field name. Typical Hubitat databases are tens or hundreds of megabytes, so a
    small bare value is treated as MB; larger bare values are treated as KB.
    Explicit KB/MB/GB suffixes always win.
    """
    if value in (None, ""):
        return None

    text = str(value).strip()
    parsed = _number(text)
    if parsed is None:
        return None

    lowered = text.lower()
    if "gb" in lowered:
        return f"{parsed:g} GB"
    if "mb" in lowered:
        return f"{parsed:g} MB"
    if "kb" in lowered:
        return f"{parsed / 1024:.1f} MB"

    # Current Hubitat builds commonly return values such as 194, meaning 194 MB.
    # Older builds return values such as 198656, meaning KB.
    megabytes = parsed / 1024 if abs(parsed) >= 4096 else parsed
    return f"{megabytes:.1f} MB" if megabytes % 1 else f"{megabytes:g} MB"


__all__ = ["format_database_size"]
