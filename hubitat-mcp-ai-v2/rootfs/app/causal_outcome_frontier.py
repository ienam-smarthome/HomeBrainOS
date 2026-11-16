"""Cross-device outcome-history coverage for model-led causal review.

Records actual current-request native receipt scopes, not which device is the
right target, whether an event occurred, controller cause, or physical effect.
The model chooses any useful *offered* read-only source and its arguments.
"""
from __future__ import annotations

from collections import Counter
import re

from investigation_source_ledger import _response, _SAFE_ID, _SAFE_FIELD

_MAX_INVENTORY = 16
_MAX_HISTORIES = 12
_MAX_EVENT_ROWS = 250
_MAX_FIELDS = 10
_MAX_EXAMPLE_VALUES = 6
_OUTCOME_ATTRIBUTES = frozenset({
    "switch", "thermostatOperatingState", "contact", "lock", "motion",
    "presence", "water", "valve", "fanSpeed", "speed", "power",
})
_NEGATIVE_OUTCOME = re.compile(
    r"\b(?:did\s+not|didn't|never|was\s+not|wasn't|has\s+not|"
    r"no\s+actual|no\s+(?:recorded|observed|matching))\b"
    r"[^\n.]{0,100}\b(?:turn(?:ed)?\s+(?:on|off)|start(?:ed)?|"
    r"activate(?:d)?|heat(?:ing)?|run(?:ning)?|operate(?:d)?|"
    r"change(?:d)?|happen(?:ed)?|occur(?:red)?|event|transition)\b",
    re.IGNORECASE,
)


def _id(value: object) -> str | None:
    if type(value) is int:
        value = str(value)
    return value if isinstance(value, str) and _SAFE_ID.fullmatch(value) else None


def _label(value: object) -> str | None:
    # Inventory labels are UNTRUSTED data, bounded for private navigation.
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or len(value) > 60 or not value.isprintable():
        return None
    return value


def causal_outcome_frontier(receipts: list[dict]) -> dict:
    """Summarize *which* device state histories were read, not what they prove.

    In particular a neighbouring sensor's idle history does not establish
    that an unread controlled output never turned on.
    """
    narrow_inventory = {}
    inventory_scopes = 0
    inventory_omitted = 0
    history: dict[str, dict] = {}
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        name, args = row.get("name"), row.get("arguments")
        args = args if isinstance(args, dict) else {}
        _, native = _response(row)
        if not isinstance(native, dict):
            continue
        if name == "hub_list_devices":
            devices = native.get("devices")
            if not isinstance(devices, list):
                continue
            inventory_scopes += 1
            # A broad/all-device inventory must not become an invitation to
            # inspect every device or a misleading shortlist of the first 16.
            focused = bool(args.get("capabilityFilter") or args.get("labelFilter"))
            if not focused or len(devices) > _MAX_INVENTORY:
                inventory_omitted += 1
                continue
            for dev in devices:
                if not isinstance(dev, dict):
                    continue
                ident = _id(dev.get("id"))
                if ident is not None:
                    narrow_inventory[ident] = _label(dev.get("label")) or ""
        elif name == "hub_get_device":
            ident = _id(native.get("id")) or _id(args.get("deviceId"))
            if ident is not None:
                narrow_inventory.setdefault(ident, _label(native.get("label")) or "")
        elif name == "hub_list_device_events":
            if native.get("source") not in ("device", None):
                continue
            events = native.get("events")
            if not isinstance(events, list):
                continue
            ident = _id(native.get("deviceId")) or _id(args.get("deviceId"))
            if ident is None:
                continue
            record = history.setdefault(ident, {
                "device_id": ident, "successful_reads": 0, "returned_rows": 0,
                "requested_filters": set(), "reported_field_values": {},
                "event_command_rows": 0,
            })
            record["successful_reads"] += 1
            record["returned_rows"] += len(events)
            filt = args.get("attribute")
            if isinstance(filt, str) and _SAFE_FIELD.fullmatch(filt):
                record["requested_filters"].add(filt)
            else:
                record["requested_filters"].add("(unfiltered)")
            for event in events[:_MAX_EVENT_ROWS]:
                if not isinstance(event, dict):
                    continue
                event_name = event.get("name")
                if not isinstance(event_name, str) or not _SAFE_FIELD.fullmatch(event_name):
                    continue
                if (event.get("type") == "command"
                        or event_name.startswith("command-")):
                    record["event_command_rows"] += 1
                if event_name in _OUTCOME_ATTRIBUTES:
                    value = event.get("value")
                    if isinstance(value, (str, int, float)) and len(str(value)) <= 24:
                        values = record["reported_field_values"].setdefault(
                            event_name, Counter()
                        )
                        values[str(value)] += 1

    all_history_ids = set(history)
    unread = [
        {"device_id": ident, "inventory_label": label}
        for ident, label in narrow_inventory.items() if ident not in all_history_ids
    ]
    read_summary = []
    for ident in sorted(history)[:_MAX_HISTORIES]:
        record = history[ident]
        read_summary.append({
            "device_id": ident,
            "successful_history_reads": record["successful_reads"],
            "returned_rows": record["returned_rows"],
            "requested_attribute_filters": sorted(record["requested_filters"])[:_MAX_FIELDS],
            "observed_state_fields": [
                {"field": field, "returned_value_counts":
                    dict(values.most_common(_MAX_EXAMPLE_VALUES))}
                for field, values in sorted(
                    record["reported_field_values"].items()
                )[:_MAX_FIELDS]
            ],
            "returned_command_rows": record["event_command_rows"],
        })
    return {
        "scope": "current_request_original_successful_receipts_only",
        "focused_inventory_device_count": len(narrow_inventory),
        "inventory_reads_seen": inventory_scopes,
        "broad_or_oversized_inventories_not_enumerated": inventory_omitted,
        "successful_device_history_target_count": len(all_history_ids),
        "device_history_scopes": read_summary,
        "device_history_scopes_omitted": max(0, len(history) - _MAX_HISTORIES),
        "focused_inventory_members_without_history": unread[:_MAX_INVENTORY],
        "unread_focused_inventory_member_count": len(unread),
        "unread_device_is_not_automatically_focal_target": True,
        "other_device_idle_does_not_rule_out_focal_outcome": True,
        "same_value_reports_do_not_verify_uninterrupted_state": True,
        "history_not_read_does_not_mean_event_absent": True,
        "frontier_does_not_verify_or_deny_user_event": True,
    }


def should_prompt_outcome_first_review(
    question: str, *, review_kind_name: str | None,
    source_frontier: dict, candidate_answer: str,
    has_action_receipt: bool = False, no_new_reads: bool = False,
) -> bool:
    """Guide existing causal review; no automatic read or extra model round."""
    return (
        review_kind_name == "causal"
        and isinstance(question, str)
        and not no_new_reads
        and not has_action_receipt
        and isinstance(source_frontier, dict)
        and (
            # Any apparent historical denial warrants scope reconciliation;
            # this is NOT proof the denial is false or that a read is required.
            bool(_NEGATIVE_OUTCOME.search(candidate_answer or ""))
            or bool(source_frontier.get("unread_focused_inventory_member_count"))
        )
    )


OUTCOME_FIRST_CHECKPOINT = """Outcome-first causal evidence checkpoint (model-led, read-only).
The user asked about a HISTORICAL change in the controlled output. Before
answering WHY it happened, establish WHETHER, WHEN and WHERE the requested
output/actuator itself reported the relevant change. The hub's current state,
a related zone/sensor, its mode, a setpoint, a listener, a location-mode event
or an app configuration is NOT a substitute for the output's event-time
operating-state/switch/command history. Idle reports from ONE device cannot
rule out shared activation or a different output's transition.

Below is a compact scope inventory from ORIGINAL successful MCP reads. It
shows which device IDs/attributes were queried and which members of a FOCUSED
inventory lack an event-history read. The inventory is evidence of possible
devices, NOT a selected focal device or proof that every member must be
queried. Select the correct controlled output from user intent and original
inventory, and judge whether a targeted READ-ONLY history or execution-source
read is proportionate and offered; the model alone chooses any tool/target/
attribute/time. A live tool catalog is availability, not a source receipt.
Do NOT fetch a tool guide instead of concrete evidence if an already-offered
read can actually answer the question. Avoid unrelated broad scans.

Do not write a categorical 'it never happened', 'only the setpoint changed'
or 'no activation occurred' from a partial/filtered/unrelated device history.
A missing row is not proof of non-occurrence; a current OFF/idle reading is not
retrospective evidence. Preserve positive evidence and exact chronology, and
separate the output report, command issuer, controller decision input and
independently verified physical outcome. If useful history is unavailable or
not proportionate, explicitly state that the outcome itself is unverified.
Never write, refresh, modify configuration or force any source call.
The original receipts, not this index, remain authoritative.
Do not mention this checkpoint."""
