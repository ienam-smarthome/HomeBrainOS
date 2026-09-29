"""Preserve literal WARN/ERROR observations during performance validation.

Generic semantic guards should correct conclusions around a log observation, not
rewrite the log payload itself. This module recognizes a cited Hubitat log source
against current-turn `hub_get_logs` evidence, restores a concise literal message,
and appends the evidence boundary as a separate sentence.
"""

from __future__ import annotations

import re
from typing import Any


_MARKDOWN_PREFIX = re.compile(
    r"^(?P<prefix>\s*(?:[-*+]\s+)?(?:\*\*[^*\n]+:\*\*\s*)?)(?P<body>.*)$",
    re.S,
)
_WARNING_WORD = re.compile(r"(?i)\b(?:warn(?:ing)?|error)\b")
_NESTED_MESSAGE = re.compile(r'"message"\s*:\s*"(?P<message>[^"\\]*(?:\\.[^"\\]*)*)')


def _sub_tool(row: dict[str, Any]) -> str:
    value = row.get("sub_tool")
    if value:
        return str(value)
    arguments = row.get("arguments")
    if isinstance(arguments, dict) and arguments.get("tool"):
        return str(arguments.get("tool"))
    return ""


def _source_key(raw_message: str) -> str:
    parts = str(raw_message or "").split("|", 3)
    if len(parts) >= 3 and parts[0].casefold() in {"app", "dev"}:
        return "|".join(parts[:3]).strip()
    return ""


def _literal_detail(raw_message: str) -> str:
    raw = str(raw_message or "").strip()
    match = _NESTED_MESSAGE.search(raw)
    if match is not None:
        detail = match.group("message")
        detail = detail.replace(r"\n", " ").replace(r'\"', '"')
    else:
        parts = raw.split("|", 3)
        detail = parts[3] if len(parts) == 4 else raw
    detail = re.sub(r"\s+", " ", detail).strip(" .\"")
    detail = detail.replace("`", "'")
    if len(detail) > 220:
        detail = detail[:217].rstrip() + "..."
    return detail


def _log_rows(evidence: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for receipt in evidence:
        if (
            not isinstance(receipt, dict)
            or receipt.get("success") is False
            or _sub_tool(receipt) != "hub_get_logs"
        ):
            continue
        details = receipt.get("details")
        if not isinstance(details, dict):
            continue
        logs = details.get("logs")
        if not isinstance(logs, list):
            continue
        for item in logs:
            if not isinstance(item, dict):
                continue
            level = str(item.get("level") or "").strip().upper()
            raw = str(item.get("message") or "").strip()
            source = _source_key(raw)
            if level not in {"WARN", "WARNING", "ERROR"} or not source or not raw:
                continue
            rows.append(
                {
                    "level": "WARN" if level == "WARNING" else level,
                    "source": source,
                    "detail": _literal_detail(raw),
                }
            )
    return rows


def guard_performance_log_observations(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Restore cited WARN/ERROR observations from authoritative current-turn logs."""

    original = str(message or "")
    if not original:
        return original, False
    observations = _log_rows(evidence)
    if not observations:
        return original, False

    changed = False
    output: list[str] = []
    for line in original.splitlines(keepends=True):
        newline = "\n" if line.endswith("\n") else ""
        core = line[:-1] if newline else line
        comparable = re.sub(r"[*_`]", "", core).casefold()
        replacement: str | None = None
        if _WARNING_WORD.search(comparable):
            for observation in observations:
                if observation["source"].casefold() not in comparable:
                    continue
                match = _MARKDOWN_PREFIX.match(core)
                prefix = match.group("prefix") if match is not None else ""
                replacement = (
                    f"{prefix}{observation['level']} from `{observation['source']}` reported "
                    f"`{observation['detail']}`. This is a recent log observation; this turn "
                    "does not establish that it caused the longer-window performance statistics."
                )
                break
        if replacement is not None and replacement != core:
            output.append(replacement + newline)
            changed = True
        else:
            output.append(core + newline)
    corrected = "".join(output)
    return corrected, changed


__all__ = ["guard_performance_log_observations"]
