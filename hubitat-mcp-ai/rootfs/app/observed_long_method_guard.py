"""Reconcile model denials of long-running methods with source-scoped Hubitat WARN rows.

Only successful current-turn structured hub_get_logs WARN/ERROR observations are
eligible. Correct false model-written absences without interpreting latency as
CPU utilisation, shared causation, or independent hub restart evidence.
"""
from __future__ import annotations

from collections import defaultdict
import re
from typing import Any

_APP_SOURCE = re.compile(r"^app\|(?P<id>[1-9]\d{1,8})\|(?P<name>[^|]+)\|")
_LONG_METHOD = re.compile(
    r"(?i)\bmethod\s+(?P<method>[A-Za-z_]\w*)\s+of\s+(?:child\s+)?app\b"
    r"[^|\r\n]{0,150}?\bran\s+for\s+"
    r"(?P<ms>(?:\d{1,3}(?:,\d{3})+|\d+))\s*ms\b"
)
_MISSING_WARN = re.compile(
    r"(?i)\b(?:no|none|zero)\s+"
    r"(?:recorded\s+|matching\s+|observed\s+)?"
    r"(?:execution(?:[\s-]+time)?|method[\s-]+duration|long[\s-]+running)"
    r"[\s-]+(?:warnings?|logs?|entries|rows)\b"
    r"|(?i:\bnot\s+observed\s+in\s+(?:the\s+)?(?:provided|returned|current)"
    r"\s+logs\b)"
)
_NUMERIC_LIMIT = re.compile(r"(?i)(?:[><]=?|more\s+than|less\s+than|over|under|above|below)\s*[\d,]+\s*ms")
_APP_ID = re.compile(r"(?i)\bapp\s+#?\s*([1-9]\d{1,8})\b")


def observed_long_method_warnings(evidence: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Group duplicate WARN/ERROR method duration rows by source app ID."""
    grouped: dict[str, dict[str, Any]] = {}
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        arguments = receipt.get("arguments")
        leaf = str(receipt.get("sub_tool") or (
            arguments.get("tool") if isinstance(arguments, dict) else ""
        ) or "")
        if leaf != "hub_get_logs":
            continue
        details = receipt.get("details")
        logs = details.get("logs") if isinstance(details, dict) else None
        if not isinstance(logs, list):
            continue
        for row in logs:
            if not isinstance(row, dict):
                continue
            if str(row.get("level") or "").upper().strip() not in {"WARN", "WARNING", "ERROR"}:
                continue
            raw = str(row.get("message") or "")[:1200]
            source = _APP_SOURCE.match(raw)
            duration = _LONG_METHOD.search(raw)
            if source is None or duration is None:
                continue
            app_id = source.group("id")
            name = source.group("name").strip()
            try:
                ms = int(duration.group("ms").replace(",", ""))
            except ValueError:
                continue
            item = grouped.setdefault(app_id, {
                "app_id": app_id, "name": name, "durations_ms": [],
                "timestamps": [], "methods": set(),
            })
            item["durations_ms"].append(ms)
            item["methods"].add(duration.group("method"))
            if row.get("date"):
                item["timestamps"].append(str(row["date"]))
    for item in grouped.values():
        item["methods"] = tuple(sorted(item["methods"]))
    return grouped


def _aliases(item: dict[str, Any]) -> tuple[str, ...]:
    raw = str(item["name"]).strip()
    stripped = re.sub(r"^\d{1,3}\s*[.:\-]\s*", "", raw).strip()
    return tuple({raw.casefold(), stripped.casefold()} - {""})


def _line_app(item_line: str, observations: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    plain = re.sub(r"[*\x60]", "", item_line).casefold()
    ids = set(_APP_ID.findall(plain))
    if ids:
        selected = [observations[app] for app in ids if app in observations]
        return selected[0] if len(selected) == 1 else None
    candidates = [
        item for item in observations.values()
        if any(re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", plain)
               for alias in _aliases(item))
    ]
    return candidates[0] if len(candidates) == 1 else None


def _summary(item: dict[str, Any]) -> str:
    values = item["durations_ms"]
    clock = ""
    if item["timestamps"]:
        start, end = min(item["timestamps"]), max(item["timestamps"])
        clock = f"; source times {start}–{end} (timezone unverified)"
    return (
        f"Current-turn scoped hub_get_logs WARN/ERROR rows for App {item['app_id']} "
        f"({item['name']}) record {len(values)} method-duration warning(s): "
        f"{min(values):,}–{max(values):,} ms{clock}. "
        "These sampled warnings do not by themselves establish the exact cause, "
        "hub-wide CPU utilisation, or a shared failure."
    )


def guard_observed_long_method_denials(
    message: str, evidence: list[dict[str, Any]]
) -> tuple[str, bool]:
    """Repair contradictory unqualified denials, preserving true narrow negatives."""
    original = str(message or "")
    observed = observed_long_method_warnings(evidence)
    if not original or not observed:
        return original, False
    lines: list[str] = []
    changed = False
    for line in original.splitlines(keepends=True):
        core = line.rstrip("\r\n")
        newline = line[len(core):]
        # Avoid editing quoted source logs, code blocks, and headings.
        if core.lstrip().startswith(("#", ">", "\x60\x60\x60")):
            lines.append(line)
            continue
        item = _line_app(core, observed)
        if item is None or _NUMERIC_LIMIT.search(core):
            lines.append(line)
            continue
        if core.strip().startswith("|") and core.strip().endswith("|"):
            cells = core.strip().strip("|").split("|")
            if len(cells) >= 3 and _MISSING_WARN.search(cells[-1]):
                cells[-1] = (f" {min(item['durations_ms']):,}–"
                             f"{max(item['durations_ms']):,} "
                             f"({len(item['durations_ms'])} WARN/ERROR rows, sampled) ")
                indent = core[: len(core) - len(core.lstrip())]
                lines.append(indent + "| " + " | ".join(c.strip() for c in cells) + " |" + newline)
                changed = True
                continue
        if _MISSING_WARN.search(core):
            prefix = re.match(r"^(\s*(?:[-*+]\s+)?)", core).group(1)
            lines.append(prefix + _summary(item) + newline)
            changed = True
        else:
            lines.append(line)
    return "".join(lines), changed


__all__ = ["observed_long_method_warnings", "guard_observed_long_method_denials"]
