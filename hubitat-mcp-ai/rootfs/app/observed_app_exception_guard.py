"""Correct denials of Hubitat overload exceptions proved by current-turn ERROR rows.

Only successful structured hub_get_logs observations are authoritative. Model
prose is used to find the claim needing correction, never to invent a log fact.
"""
from __future__ import annotations
import re
from typing import Any

_OVERLOAD = re.compile(r"\bLimitExceededException\b.{0,160}?\bApp\s+([1-9]\d{0,8})\s+generates\s+excessive\s+hub\s+load\b", re.I)
_DENIAL = re.compile(r"(?i)\b(?:no|none|without|absent|not\s+(?:found|observed|recorded))\b[^.!?\n]{0,150}?(?:LimitExceededException|excessive[\s-]+hub[\s-]+load|load\s+exceptions?)\b")
_ONLY = re.compile(r"(?i)(?:\bcausation\b|\bexceptions?\b)[^.!?\n]{0,110}?\bonly\s+(?:proven|confirmed|observed|recorded)\s+for\b")
_PROVEN = re.compile(r"(?i)^\s*(?:[-*+]\s*)?proven\s+causation\s*:")
_APP = re.compile(r"(?i)\bApp\s+([1-9]\d{0,8})\b")
_SENTENCE = re.compile(r"(?<=[.!?])([ \t]+)")
_EXCLUSIVE = re.compile(r"(?i)(?:\bonly\b[^.!?\n]{0,90}\b(?:exceptions?|errors?|excessive\s+hub\s+load)\b|\b(?:exceptions?|errors?|excessive\s+hub\s+load)\b[^.!?\n]{0,90}\bonly\b)")


def observed_exception_app_ids(evidence: list[dict[str, Any]]) -> tuple[str, ...]:
    apps: set[str] = set()
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        args = receipt.get("arguments")
        leaf = str(receipt.get("sub_tool") or (args.get("tool") if isinstance(args, dict) else "") or "")
        if leaf != "hub_get_logs":
            continue
        details = receipt.get("details")
        logs = details.get("logs") if isinstance(details, dict) else None
        if not isinstance(logs, list):
            continue
        for row in logs:
            if not isinstance(row, dict) or str(row.get("level") or "").strip().upper() not in {"ERROR", "ERR"}:
                continue
            match = _OVERLOAD.search(str(row.get("message") or "")[:900])
            if match:
                apps.add(match.group(1))
    return tuple(sorted(apps, key=int))


def _table_aliases(message: str, ids: tuple[str, ...]) -> dict[str, set[str]]:
    """Use a model's same-row labels ONLY to locate the claim, never as proof."""
    aliases: dict[str, set[str]] = {app_id: set() for app_id in ids}
    for row in message.splitlines():
        if not row.strip().startswith("|") or row.count("|") < 3:
            continue
        cells = [re.sub(r"[*\x60]", "", cell).strip() for cell in row.strip().strip("|").split("|")]
        for i, cell in enumerate(cells):
            match = _APP.fullmatch(cell) or re.fullmatch(r"([1-9]\d{2,8})", cell)
            if match is None or match.group(1) not in aliases:
                continue
            label = cells[i - 1] if i else ""
            for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{4,}", label):
                if token.casefold() not in {"device", "status", "report", "connect", "notifier", "energy", "meter", "usage", "system"}:
                    aliases[match.group(1)].add(token.casefold())
    return aliases


def _target_matches(sentence: str, prior: str, ids: tuple[str, ...], aliases: dict[str, set[str]]) -> bool:
    clean = re.sub(r"[*\x60]", "", sentence)
    # A scoped single-app negative must not be contradicted by other apps.
    mentioned = set(_APP.findall(clean))
    if mentioned and not (mentioned & set(ids)):
        return False
    match = re.search(r"(?i)\b(?:for|from|involving)\b(.{0,160})$", clean)
    if match is None:
        return True  # blanket statement, directly contradicted by any exception
    subject = match.group(1)
    explicit = set(_APP.findall(subject))
    if explicit:
        return bool(explicit & set(ids))
    near = subject
    if re.search(r"(?i)\b(?:these|both|those|the two|the three)\b", subject):
        near += " " + prior[-400:]
    lower = near.casefold()
    return any(re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", lower)
               for app_id in ids for alias in aliases.get(app_id, ()))


def guard_observed_app_exception_denials(message: str, evidence: list[dict[str, Any]]) -> tuple[str, bool]:
    """Correct categorical absence/exclusivity errors without inferring causal links."""
    original = str(message or "")
    ids = observed_exception_app_ids(evidence)
    if not original or not ids:
        return original, False
    aliases = _table_aliases(original, ids)
    observed = ("Current-turn hub_get_logs ERROR rows explicitly report "
                "LimitExceededException (excessive hub load) for "
                + ", ".join("App " + app_id for app_id in ids)
                + ". This verifies sampled exceptions, not a shared root cause, "
                "whole-hub CPU utilisation or user-visible performance impact.")
    changed = False
    rendered_lines: list[str] = []
    for line in original.splitlines(keepends=True):
        # Never turn Markdown section headings into a diagnostic correction.
        if line.lstrip().startswith(("#", "\x60\x60\x60")):
            rendered_lines.append(line)
            continue
        parts = _SENTENCE.split(line)
        for i in range(0, len(parts), 2):
            sentence = parts[i]
            if not sentence.strip():
                continue
            plain = re.sub(r"[*\x60]", "", sentence)
            denial = bool(_DENIAL.search(plain))
            exclusivity = len(ids) > 1 and bool(_ONLY.search(plain) or _PROVEN.search(plain) or (_EXCLUSIVE.search(plain) and _APP.search(plain)))
            if not denial and not exclusivity:
                continue
            if denial and not _target_matches(plain, "".join(parts[:i]), ids, aliases):
                continue
            if exclusivity and not re.search(r"(?i)\b(?:exceptions?|errors?|causation|excessive\s+hub\s+load)\b", plain):
                continue
            leading = re.match(r"^(\s*(?:[-*+]\s+|>\s+)?)", sentence).group(1)
            ending = "\n" if sentence.endswith("\n") else ""
            parts[i] = leading + observed + ending
            changed = True
        rendered_lines.append("".join(parts))
    return "".join(rendered_lines), changed


__all__ = ["observed_exception_app_ids", "guard_observed_app_exception_denials"]
