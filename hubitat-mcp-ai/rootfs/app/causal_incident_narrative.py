"""Short evidence-grounded incident storytelling helpers.

Only source-timed switch reports make cycle durations. Names must come from
scoped and verified Hubitat reads. Sensor collector receipts do not prove
original sensor event times or upstream command issuers.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


def safe_device_label(raw: Any, device_id: str, *, fallback: str = "Device") -> str:
    name = str(raw or "").strip()
    forbidden = ("|", chr(96), "<", ">", "[", "]", "{", "}")
    if (not name or len(name) > 72
            or any(ord(char) < 32 for char in name)
            or any(char in name for char in forbidden)
            or name.isdecimal()):
        return f"{fallback} (device {device_id})"
    return name


def verified_input_label(facts: Mapping[str, Any], ident: Any) -> str:
    device_id = str(ident or "")
    names = facts.get("input_device_labels") or {}
    raw = names.get(device_id) if isinstance(names, Mapping) else None
    return safe_device_label(raw, device_id, fallback="Motion sensor")


def _when(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return value.astimezone(timezone.utc) if value.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def _duration(start: datetime, end: datetime) -> str:
    seconds = round((end - start).total_seconds())
    if seconds < 60:
        return f"{seconds} sec"
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes} min" + (f" {seconds} sec" if seconds else "")


def source_cycle_timeline(
    source: Mapping[str, Sequence[Mapping[str, Any]]],
    targets: Sequence[str],
    names: Mapping[str, str],
    *,
    max_rows: int = 12,
) -> str | None:
    """Render full paired light cycles only when BOTH source streams agree.

    Both histories must alternate ON/OFF with each corresponding transition
    within two seconds. Never create missing events or durations.
    """
    if len(targets) != 2:
        return None
    first, second = (str(targets[0]), str(targets[1]))
    a, b = list(source.get(first) or []), list(source.get(second) or [])
    if len(a) < 2 or len(a) != len(b) or len(a) % 2:
        return None
    if any(str(row.get("value") or "").lower() != ("on" if i % 2 == 0 else "off")
           for i, row in enumerate(a)):
        return None
    if any(str(row.get("value") or "").lower() != ("on" if i % 2 == 0 else "off")
           for i, row in enumerate(b)):
        return None
    source_a = [_when(row.get("date")) for row in a]
    source_b = [_when(row.get("date")) for row in b]
    if any(x is None for x in source_a + source_b):
        return None
    if any(source_a[i] >= source_a[i + 1] or source_b[i] >= source_b[i + 1]
           for i in range(len(a) - 1)):
        return None
    if any(abs((source_b[i] - source_a[i]).total_seconds()) > 2
           for i in range(len(a))):
        return None
    n = len(a) // 2
    rows = [
        f"| {source_a[i].strftime('%H:%M:%S')} | "
        f"{source_a[i+1].strftime('%H:%M:%S')} | "
        f"{_duration(source_a[i], source_a[i+1])} |"
        for i in range(0, min(len(a), 2 * max_rows), 2)
    ]
    suffix = (f"\nShowing {len(rows)} of {n} recorded cycles."
              if n > len(rows) else "")
    return (
        "**Timeline — recorded lighting cycles (UTC)**\n\n"
        "| Lights ON | Lights OFF | Time on |\n"
        "|---|---|---|\n"
        + "\n".join(rows)
        + suffix + "\n\n"
        + f"Times are from {names[first]}; {names[second]} followed "
          "roughly one second later on each recorded change. "
          "These are source-timestamped state reports, not confirmed "
          "upstream commands."
    )


__all__ = ["safe_device_label", "verified_input_label", "source_cycle_timeline"]
