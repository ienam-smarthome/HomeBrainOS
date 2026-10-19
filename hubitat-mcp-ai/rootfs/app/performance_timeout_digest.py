"""Evidence-only performance report when a model synthesis times out.

Never reuse an unverified model draft. Only accept successful current-request
tool payloads and label everything as sampled measurements or next checks.
"""
from __future__ import annotations

from collections import Counter
import json
import re
from typing import Any


def _parse(text: Any) -> dict[str, Any]:
    try:
        raw = text if isinstance(text, dict) else json.loads(str(text or ""))
    except (ValueError, TypeError):
        return {}
    for _ in range(3):
        if not isinstance(raw, dict):
            return {}
        if isinstance(raw.get("result"), dict):
            raw = raw["result"]
        elif isinstance(raw.get("data"), dict):
            raw = raw["data"]
        else:
            break
    return raw if isinstance(raw, dict) else {}


def _find(data: Any, keys: tuple[str, ...]) -> Any:
    if isinstance(data, dict):
        for key in keys:
            if key in data and data[key] not in (None, ""):
                return data[key]
        for val in data.values():
            found = _find(val, keys)
            if found not in (None, ""):
                return found
    elif isinstance(data, list):
        for val in data[:12]:
            found = _find(val, keys)
            if found not in (None, ""):
                return found
    return None


def _number(value: Any) -> float | None:
    try:
        return float(str(value).replace("%", "").replace(",", ""))
    except (ValueError, TypeError):
        return None


def _display(value: Any) -> str:
    number = _number(value)
    return f"{number:.2f}".rstrip("0").rstrip(".") if number is not None else "unknown"


def _name(value: Any) -> str:
    # Device/app names are untrusted presentation data, not markup or code.
    s = re.sub(r"[\r\n|<>{}\[\]*\x60]", " ", str(value or ""))
    return re.sub(r"\s+", " ", s).strip()[:65]


def _kind(row: dict[str, Any]) -> str:
    args = row.get("arguments")
    return str(
        row.get("sub_tool")
        or (args.get("tool") if isinstance(args, dict) else None)
        or ""
    )


def _sampled_warning_groups(evidence: list[dict[str, Any]]) -> list[tuple[str, str, int]]:
    counts: Counter[tuple[str, str]] = Counter()
    for row in evidence:
        if (
            not isinstance(row, dict)
            or row.get("success") is not True
            or _kind(row) != "hub_get_logs"
        ):
            continue
        details = row.get("details")
        rows = details.get("logs") if isinstance(details, dict) else None
        if not isinstance(rows, list):
            continue
        for event in rows[:200]:
            if not isinstance(event, dict):
                continue
            level = str(event.get("level") or "").casefold()
            if level not in ("error", "warn", "warning"):
                continue
            parts = str(event.get("message") or "").split("|", 3)
            if len(parts) < 4 or parts[0] not in ("dev", "app"):
                continue
            name = _name(parts[2])
            if name:
                counts[(name, "error" if level == "error" else "warning")] += 1
    return [
        (name, level, count)
        for (name, level), count in sorted(
            counts.items(), key=lambda item: (-item[1], item[0][0])
        )[:5]
    ]


def render_performance_timeout_digest(
    *,
    captured: dict[str, str],
    evidence: list[dict[str, Any]],
    job_digest: dict[str, Any] | None = None,
    timeout_seconds: float = 30,
) -> str:
    """Report observed measurements without claiming completed AI analysis."""
    available = {
        _kind(row) for row in evidence if isinstance(row, dict)
        and row.get("success") is True and row.get("mutates") is not True
    }
    lines = [
        "## Hubitat performance — verified partial report",
        f"AI synthesis exceeded its {timeout_seconds:g}-second limit. "
        "The following values come from successful read-only sources. "
        "This is not a completed whole-hub diagnosis or repair plan.",
        "",
    ]
    metrics = _parse(captured.get("hub_get_metrics")) if "hub_get_metrics" in available else {}
    facts = []
    for label, keys, unit in (
        ("Free memory", ("freeMemoryMB", "free_memory_mb", "memoryFreeMB"), "MB"),
        ("Hub temperature", ("temperatureC", "internalTemperatureC", "hubTemperatureC"), "°C"),
        ("Database size", ("databaseSizeMB", "databaseMB", "dbSizeMB"), "MB"),
    ):
        value = _find(metrics, keys)
        if _number(value) is not None:
            facts.append(f"{label}: {_display(value)} {unit}")
    alerts = _find(metrics, ("healthAlerts",))
    if isinstance(alerts, list) and not alerts:
        facts.append("Current health alerts: none reported")
    if facts:
        lines.extend(["### Current metrics", *("- " + f for f in facts), ""])

    performance = _parse(captured.get("hub_get_performance_stats")) if "hub_get_performance_stats" in available else {}
    leaders = []
    for kind, field in (("App", "appStats"), ("Device", "deviceStats")):
        rows = performance.get(field)
        if not isinstance(rows, list):
            continue
        ranked = sorted(
            (r for r in rows if isinstance(r, dict) and r.get("name")
             and _number(r.get("pctTotal")) is not None),
            key=lambda r: _number(r.get("pctTotal")) or 0, reverse=True,
        )
        for item in ranked[:3]:
            leaders.append(
                f"- **{kind} {_name(item['name'])}:** "
                f"{_display(item['pctTotal'])}% reported uptime; "
                f"{_display(item.get('pctBusy'))}% class busy share; "
                f"{_display(item.get('averageMs'))} ms average."
            )
    if leaders:
        lines.extend([
            "### Measured performance leaders", *leaders,
            "Performance shares are measurements, not proof of faulty code.",
            "",
        ])

    if "hub_get_jobs" in available and isinstance(job_digest, dict):
        total = _number(job_digest.get("reportedJobs"))
        examined = _number(job_digest.get("rowsExamined"))
        if total is not None and examined is not None:
            lines.extend([
                "### Scheduled jobs",
                f"- {int(total)} reported jobs; {int(examined)} rows examined.",
                "Job counts do not establish avoidable CPU work or safe schedule changes.",
                "",
            ])

    warning_groups = _sampled_warning_groups(evidence)
    if warning_groups:
        lines.append("### Sampled warning/error sources")
        for name, level, count in warning_groups:
            lines.append(f"- **{name}:** {count} {level} log rows in returned samples.")
        lines.extend([
            "Counts are sampled rows, not an exhaustive 24-hour fault history.",
            "",
        ])

    lines.extend([
        "### Safe next checks",
        "- Check the matched warning/error sources and their settings before "
        "changing polling, retries, or connections."
        if warning_groups else
        "- Retrieve source-scoped WARN/ERROR logs before attributing load to faults.",
        "- Review rule and device dependencies before retiring or changing schedules.",
        "- No devices, rules, or configuration were changed.",
        "",
        "**Read coverage:** " + (", ".join(sorted(available)) or "none") + ". "
        "Unqueried drivers, rules, history and log ranges remain unchecked.",
    ])
    return "\n".join(lines)


__all__ = ["render_performance_timeout_digest"]
