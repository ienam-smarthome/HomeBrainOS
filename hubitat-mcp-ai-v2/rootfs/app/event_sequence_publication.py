"""Conservative source-bound chronology floor for historical read-only prose.

Only typed SAME-DEVICE original event rows can establish a dated state change.
A stored current switch value, a command request, a notified listener or an
app log is not an intervening ON/OFF observation or a decision trigger.
This module never reads sources, selects devices, changes a command or fabricates
a state. Its bounded rejection is *not* a general language truth verifier.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re

from investigation_source_ledger import _response
from native_device_event_receipt import original_device_event_history

# Recognise only AFFIRMATIVE asserted physical/state actions, not imperative
# instructions or a quoted hypothetical. Source absence cannot prove that
# the event never occurred: it only denies publishing an asserted transition.
_STATE_CHANGE = re.compile(
    r"\b(?:was|were|has|had|is)\s+(?:actually\s+)?(?:been\s+)?"
    r"(?:turned|switched)\s+(?:back\s+)?(?P<state>on|off)\b"
    r"|\b(?:turned|switched)\s+back\s+(?P<state2>on|off)\b",
    re.I,
)
_SPECULATIVE = re.compile(
    r"\b(?:might|may|could|possibly|perhaps|if|cannot|can't|unknown|"
    r"not\s+(?:proven|confirmed|verified|observed))\b", re.I,
)
# A *latest command* said to be before an observed health update is
# contradicted when the source actually dates the command AFTER that update.
# This is a relation between two native event categories, never an assumption
# about control execution or device state.
_COMMAND_BEFORE_STATUS = re.compile(
    r"\b(?:latest|last|most\s+recent|command|off-command|on-command)\b"
    r"[^.!?\n]{0,145}\b(?:before|preceded)\b"
    r"[^.!?\n]{0,120}\b(?:health|status)\b",
    re.I,
)
_HEALTH_AS_MEASUREMENT = re.compile(
    r"\b(?:latest|newest|most\s+recent)\s+(?:independently\s+)?"
    r"(?:dated\s+)?measurement\b"
    r"[\s\S]{0,165}\bhealthStatus\b", re.I,
)


def _time(value: object) -> datetime | None:
    if not isinstance(value, str) or len(value) > 52:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(timezone.utc) if dt.tzinfo is not None else None


def _source_rows(receipts: list[dict]) -> tuple[str | None, list[dict]]:
    targets = set()
    ordered: dict[tuple, dict] = {}
    for row in receipts[:24]:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if row.get("operation_executed") is False:
            continue
        if row.get("name") != "hub_list_device_events":
            continue
        original = original_device_event_history(row)
        if original is None:
            continue
        device_id, _, events = original
        targets.add(str(device_id))
        for event in events[:300]:
            if not isinstance(event, dict):
                continue
            stamp = _time(event.get("date"))
            name = event.get("name")
            if (stamp is None or not isinstance(name, str)
                    or len(name) > 70 or not re.fullmatch(
                        r"[A-Za-z][A-Za-z0-9_.-]{0,69}", name
                    )):
                continue
            command = name.startswith("command-") or event.get("type") == "command"
            state = event.get("value")
            item = {
                "name": name, "date": stamp, "command": command,
                "value": state.lower() if isinstance(state, str) else None,
            }
            ordered[(device_id, name, stamp, item["value"])] = item
    # Only an unambiguous SAME-DEVICE timeline is eligible for a publication
    # check. Multi-device investigations are left to their existing guards.
    if len(targets) != 1:
        return None, []
    return next(iter(targets)), sorted(ordered.values(), key=lambda x: x["date"])


def source_sequence_publication_check(
    question: str, answer: str, receipts: list[dict],
) -> dict:
    result = {"status": "not_applicable", "reason": None, "source_note": ""}
    if not isinstance(question, str) or not isinstance(answer, str) or not answer:
        return result
    device_id, events = _source_rows(receipts)
    if device_id is None or not events:
        return result

    commands = [e for e in events if e["command"]]
    status_rows = [
        e for e in events
        if not e["command"] and e["name"] == "healthStatus"
        and e["value"] in ("online", "offline", "unknown")
    ]
    stated_changes = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", answer):
        if _SPECULATIVE.search(sentence):
            continue
        for match in _STATE_CHANGE.finditer(sentence):
            stated_changes.append(match.group("state") or match.group("state2"))

    reasons = []
    for state in stated_changes:
        # A native command-on is a REQUEST, not an observed ON event.
        matching = [
            row for row in events
            if not row["command"] and row["name"] == "switch"
            and row["value"] == state.lower()
        ]
        last_opposite_command = max(
            (e["date"] for e in commands
             if e["name"] == "command-" + ("off" if state.lower() == "on" else "on")),
            default=None,
        )
        if last_opposite_command and not any(
            e["date"] > last_opposite_command for e in matching
        ):
            reasons.append("intervening_switch_change_not_in_returned_events")
            break
    if status_rows and commands and _COMMAND_BEFORE_STATUS.search(answer):
        latest_command = max(commands, key=lambda e: e["date"])
        latest_status = max(status_rows, key=lambda e: e["date"])
        if latest_command["date"] > latest_status["date"]:
            reasons.append("command_status_order_contradicts_source_timestamps")
    if (status_rows and "measurement" in question.lower()
            and _HEALTH_AS_MEASUREMENT.search(answer)):
        reasons.append("health_status_event_mislabelled_as_measurement")

    if not reasons:
        result["status"] = "no_detected_contradiction"
        return result
    notes = [
        "**Original same-device event chronology (bounded source):**",
    ]
    if status_rows:
        latest_status = max(status_rows, key=lambda e: e["date"])
        notes.append(
            f"- `healthStatus` {latest_status['value']} reported at "
            f"{latest_status['date'].isoformat()}; this is a status event, "
            "not a dated power/energy measurement."
        )
    if commands:
        latest_command = max(commands, key=lambda e: e["date"])
        notes.append(
            f"- `{latest_command['name']}` command row recorded at "
            f"{latest_command['date'].isoformat()}; a command does not "
            "establish subsequent switching or physical effect."
        )
    if status_rows and commands:
        gap = (latest_command["date"] - latest_status["date"]).total_seconds()
        relation = "after" if gap > 0 else "before" if gap < 0 else "at the same time as"
        notes.append(
            f"- The last command is {abs(gap):.3f} seconds {relation} "
            "the newest returned health-status report."
        )
    notes.append(
        "A current stored switch attribute has no attribute-specific event "
        "timestamp here. No missing intervening switch event, internal cause "
        "or complete event-history coverage can be inferred from these rows."
    )
    return {
        "status": "unsafe",
        "reason": ",".join(dict.fromkeys(reasons)),
        "source_note": "\n".join(notes),
        "focal_device_id": device_id,
    }
