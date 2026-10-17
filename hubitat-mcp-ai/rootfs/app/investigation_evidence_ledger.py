"""Fail-closed, evidence-first validation of recorded device commands.

Pure and read-only. This ledger does not infer a state transition from a
command event, and never invents a root cause. Duplicate records are removed
by stable command identity. Only explicitly successful tool receipts count.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}T")
_COMMAND = re.compile(r"^command[-_]", re.I)
_ABSENCE = re.compile(
    r"(?i)\b(?:no|zero)\s+(?:recorded\s+)?(?:commands?|command\s+events?)"
    r"\b[^\n.!?]{0,100}\b(?:on|for|from|dated)\s+"
    r"(?P<date>\d{1,2}\s+[A-Za-z]+\s+\d{4}|\d{4}-\d{2}-\d{2})"
    r"|\b(?:no|zero)\s+(?:commands?|command\s+events?)"
    r"\b[^\n.!?]{0,100}\b(?:on|for|from|dated)\s+"
    r"(?P<iso>\d{4}-\d{2}-\d{2})"
    r"|\bno\s+commands?\s+issued\s+[^\n.!?]{0,120}?"
    r"(?:were|was)\s+(?:identified|recorded|found)\s+"
    r"for\s+(?:the\s+date\s+of\s+)?"
    r"(?P<issued_date>\d{1,2}\s+[A-Za-z]+\s+\d{4}|\d{4}-\d{2}-\d{2})",
)

# Additional natural-language form seen in a live failing investigation:
# "No switch=on or command events were recorded for 12 October 2026".
# Sentence must deny commands *for an entire date*, not at the focal time.
_MIXED_ABSENCE = re.compile(
    r"(?i)\bno\s+(?:\x60?switch\s*=\s*on\x60?\s+or\s+)?"
    r"\x60?commands?\x60?\s+(?:events?\s+)?"
    r"(?:were|was)?\s*(?:recorded|observed|identified|found)\s+"
    r"(?:on|for|from|dated)\s+(?:the\s+date\s+of\s+)?"
    r"(?P<date>\d{1,2}\s+[A-Za-z]+\s+\d{4}|\d{4}-\d{2}-\d{2})"
)

_MONTHS = {m.lower(): n for n, m in enumerate(
    ("January", "February", "March", "April", "May", "June",
     "July", "August", "September", "October", "November", "December"), 1
)}


@dataclass(frozen=True)
class CommandFact:
    timestamp: str
    name: str
    producer: str
    device: str


def command_facts(evidence: list[dict[str, Any]]) -> list[CommandFact]:
    found: dict[tuple[str, str, str, str], CommandFact] = {}
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        details = receipt.get("details")
        if not isinstance(details, dict):
            continue
        device = str(details.get("label") or "")
        for key in ("events", "commandEvents", "boundaryEvents", "observedEvents", "correlationEvents"):
            rows = details.get(key)
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                name = str(row.get("name") or "")
                stamp = row.get("date")
                if not _COMMAND.match(name) or not isinstance(stamp, str) or not _DATE.match(stamp):
                    continue
                origin = row.get("producedBy")
                producer = str(origin.get("label") or "") if isinstance(origin, dict) else ""
                fact = CommandFact(stamp, name, producer, device)
                found[(stamp, name, producer, device)] = fact
    return sorted(found.values(), key=lambda fact: fact.timestamp)


def _date_key(label: str) -> str | None:
    from datetime import date
    value = label.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            return None
    match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", value)
    if not match:
        return None
    month = _MONTHS.get(match.group(2).lower())
    if month is None:
        return None
    try:
        return date(int(match.group(3)), month, int(match.group(1))).isoformat()
    except ValueError:
        return None


def reconcile_command_denials(message: str, evidence: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Replace only an explicit false command-absence sentence with facts.

    A missing focal transition remains unresolved even if there is another
    command on the same date. Do not report a missing log query as evidence.
    """
    facts = command_facts(evidence)
    if not facts:
        return message, []
    contradictions: list[dict[str, Any]] = []
    def replacement(match: re.Match[str]) -> str:
        # A command at 07:25 cannot refute absence precisely AT 08:16.
        # Reconcile whole-date denials only; preserve focal-time negatives.
        if re.search(
            r"(?i)\b(?:at|around|approximately)\s+\d{1,2}:\d{2}",
            match.group(0),
        ):
            return match.group(0)
        day = _date_key(match.group("date") or match.group("iso")
                        or match.group("issued_date") or "")
        relevant = [fact for fact in facts if fact.timestamp.startswith(day)] if day else []
        if not relevant:
            return match.group(0)
        fact = relevant[0]
        contradictions.append({"kind": "false_command_absence", "date": day, "observed_count": len(relevant)})
        source = f" by {fact.producer}" if fact.producer else ""
        device = f" for {fact.device}" if fact.device else ""
        return (
            f"A {fact.name} was recorded{device} at {fact.timestamp}{source}"
            f" ({len(relevant)} distinct matching command event(s) observed). "
            "This does not establish that the separate requested device-state transition occurred"
        )
    corrected = _ABSENCE.sub(replacement, str(message or ""))
    corrected = _MIXED_ABSENCE.sub(replacement, corrected)
    return corrected, contradictions
