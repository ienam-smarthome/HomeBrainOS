"""Source-neutral arithmetic over *observed* numeric time-series rows.

This module performs no MCP reads and never asserts that source histories are
complete. The caller must establish target identity, attribute, provenance,
retention and pagination separately. No inferred physical crossing times.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable
import math
import re

_OPERATORS = {
    "gt": lambda x, y: x > y,
    "gte": lambda x, y: x >= y,
    "lt": lambda x, y: x < y,
    "lte": lambda x, y: x <= y,
    "eq": lambda x, y: x == y,
    "ne": lambda x, y: x != y,
}
_NUMERIC = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")


def _number(value: Any) -> Decimal | None:
    """Accept scalar numbers, not booleans, embedded prose or NaN/Inf."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    text = str(value).strip()
    if not _NUMERIC.fullmatch(text):
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _instant(value: Any) -> datetime | None:
    """Require timezone-aware ISO datetimes, never ambiguous local naive time."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def observed_transition(
    rows: Iterable[dict[str, Any]],
    *,
    from_operator: str,
    from_threshold: int | float | str | Decimal,
    to_operator: str,
    to_threshold: int | float | str | Decimal,
    choose_from: str = "last",
) -> dict[str, Any]:
    """Locate the first later matching observation after the chosen start.

    Rows contain ``timestamp`` (ISO 8601 with UTC offset) and numeric
    ``value``. The result does not attest to source completeness, device
    identity or exact physical crossing. Caller must attach those receipts.
    """
    if from_operator not in _OPERATORS or to_operator not in _OPERATORS:
        raise ValueError("unsupported comparison operator")
    if choose_from not in ("first", "last"):
        raise ValueError("choose_from must be first or last")
    a, b = _number(from_threshold), _number(to_threshold)
    if a is None or b is None:
        raise ValueError("thresholds must be finite scalar numbers")

    points: list[tuple[datetime, Decimal, int]] = []
    total = 0
    for index, row in enumerate(rows):
        total += 1
        if not isinstance(row, dict):
            continue
        instant = _instant(row.get("timestamp"))
        numeric = _number(row.get("value"))
        if instant is not None and numeric is not None:
            points.append((instant, numeric, index))
    points.sort(key=lambda p: (p[0], p[2]))
    response: dict[str, Any] = {
        "status": "no_valid_observations",
        "observed_rows": len(points),
        "rejected_rows": total - len(points),
        "first_sample_utc": points[0][0].isoformat() if points else None,
        "last_sample_utc": points[-1][0].isoformat() if points else None,
        "from": {"operator": from_operator, "threshold": str(a)},
        "to": {"operator": to_operator, "threshold": str(b)},
        "source_coverage_verified": False,
        "exact_physical_crossing_verified": False,
        "qualification": (
            "Results apply only to supplied recorded samples. A gap between "
            "observations is not the physical threshold crossing time; "
            "history retention, pages and source identity require separate proof."
        ),
        "start": None,
        "end": None,
        "observed_elapsed_seconds": None,
    }
    if not points:
        return response
    matching = [i for i, (_, v, _) in enumerate(points)
                if _OPERATORS[from_operator](v, a)]
    if not matching:
        response["status"] = "start_not_observed_in_supplied_rows"
        return response
    start_idx = matching[-1] if choose_from == "last" else matching[0]
    t0, v0, _ = points[start_idx]
    response["start"] = {"timestamp_utc": t0.isoformat(), "value": str(v0)}
    for t1, v1, _ in points[start_idx + 1:]:
        # Simultaneous reports cannot establish a later observation.
        if t1 > t0 and _OPERATORS[to_operator](v1, b):
            response["status"] = "observed_interval"
            response["end"] = {"timestamp_utc": t1.isoformat(), "value": str(v1)}
            response["observed_elapsed_seconds"] = int((t1 - t0).total_seconds())
            return response
    response["status"] = "later_end_not_observed_in_supplied_rows"
    return response


__all__ = ["observed_transition"]
