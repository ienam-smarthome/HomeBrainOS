"""Read-only source-bound projections for bounded original V2 inventory and log receipts.

The model chooses native reads; these projections never select or retry tools.
Original Technical JSON receipts are not mutated. No action paths are covered.
"""
from __future__ import annotations

from collections import defaultdict
import math
import re

from investigation_source_ledger import _response
from read_only_receipt_fallback import _returned_past_log_groups

_RANGE = re.compile(
    r"\b(?P<field>[A-Za-z][A-Za-z0-9_]{0,31})"
    r"(?:\s+value)?\s+(?:from|between)\s+"
    r"(?P<low>\d+(?:\.\d{1,3})?)\s+(?:to|and)\s+"
    r"(?P<high>\d+(?:\.\d{1,3})?)\b", re.I,
)
_SAFE_FIELD = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,31}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
_SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _().+\-]{0,79}$")
_NUMBER = re.compile(r"^[+-]?\d{1,8}(?:\.\d{1,6})?$")
_CURRENT_STATES = ("switch", "level", "contact", "motion", "temperature",
                   "humidity", "power", "energy", "battery", "healthStatus",
                   "thermostatOperatingState", "heatingSetpoint", "coolingSetpoint")
_KNOWN_STATES = frozenset({
    "on", "off", "open", "closed", "active", "inactive", "present", "not present",
    "online", "offline", "idle", "heating", "cooling", "dry", "wet",
    "locked", "unlocked", "running", "stopped", "auto", "heat", "cool",
})
_MAX_RECEIPTS = 20
_MAX_PAGE_ROWS = 500
_MAX_SNAPSHOT_DEVICES = 6


def _safe_number(raw: object) -> float | None:
    if type(raw) in (int, float):
        number = float(raw)
    elif isinstance(raw, str) and _NUMBER.fullmatch(raw.strip()):
        number = float(raw.strip())
    else:
        return None
    return number if math.isfinite(number) else None


def _safe_device_id(raw: object) -> str | None:
    if type(raw) is int and raw >= 0:
        raw = str(raw)
    return raw if isinstance(raw, str) and _SAFE_ID.fullmatch(raw) else None


def _print_number(value: float) -> str:
    return str(int(value)) if value.is_integer() else ("%g" % value)


def bounded_numeric_inventory_answer(
    question: str, receipts: list[dict],
) -> str | None:
    """Count unique IDs from actual returned projected pages, not unseen rows.

    Conflicting offsets, original counts or native page totals fail closed.
    Source-reported total does NOT prove that unread devices lack matches.
    """
    if (not isinstance(question, str)
            or not re.search(r"\b(?:count|how many)\b", question, re.I)
            or not re.search(r"\bdevices?\b", question, re.I)):
        return None
    match = _RANGE.search(question)
    if match is None:
        return None
    field = match.group("field")
    field = field[:1].lower() + field[1:]
    if not _SAFE_FIELD.fullmatch(field):
        return None
    low = _safe_number(match.group("low"))
    high = _safe_number(match.group("high"))
    if low is None or high is None or low > high:
        return None

    pages = []
    for receipt in receipts[:_MAX_RECEIPTS]:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        if receipt.get("name") != "hub_list_devices":
            continue
        args = receipt.get("arguments")
        if (not isinstance(args, dict) or args.get("format") != "summary"
                or args.get("labelFilter") or args.get("deviceId")
                or args.get("attributeNames") != [field]):
            continue
        _, native = _response(receipt)
        if not isinstance(native, dict):
            continue
        rows = native.get("devices")
        offset = native.get("offset")
        total = native.get("total")
        reported_count = native.get("count")
        has_more = native.get("hasMore")
        if (not isinstance(rows, list) or len(rows) > _MAX_PAGE_ROWS
                or type(offset) is not int or offset < 0
                or type(total) is not int or total < 0
                or type(reported_count) is not int or reported_count != len(rows)
                or type(has_more) is not bool or total < offset + len(rows)):
            return None
        pages.append((offset, rows, total, has_more))
    if not pages:
        return None
    source_totals = {p[2] for p in pages}
    if len(source_totals) != 1:
        return None
    total = source_totals.pop()

    indexed: dict[int, tuple[str, object]] = {}
    for offset, rows, _, _ in pages:
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                return None
            device_id = _safe_device_id(row.get("id"))
            current = row.get("currentStates")
            if device_id is None or not isinstance(current, dict):
                return None
            pos = offset + i
            value = current.get(field)
            if pos in indexed and indexed[pos] != (device_id, value):
                return None
            indexed[pos] = device_id, value
    ids: dict[str, object] = {}
    for ident, value in indexed.values():
        if ident in ids and ids[ident] != value:
            return None
        ids[ident] = value
    if not ids:
        return None
    ordered = sorted(ids.items(), key=lambda pair: pair[0])
    qualifying = []
    missing = 0
    nonnumeric = 0
    for ident, raw in ordered:
        if raw is None:
            missing += 1
            continue
        numeric = _safe_number(raw)
        if numeric is None:
            nonnumeric += 1
        elif low <= numeric <= high:
            qualifying.append((ident, numeric))
    covered_positions = set(indexed)
    complete = (len(covered_positions) == total and len(ids) == total
                and min(covered_positions) == 0
                and max(covered_positions) == total - 1
                and any(not page[3] and page[0] + len(page[1]) == total for page in pages))
    unseen = max(0, total - len(covered_positions))
    unit = "%" if (field.lower() == "battery"
                    or re.search(r"\bpercent\b|%", question, re.I)) else ""
    lines = [
        f"**Source-counted {field} range {_print_number(low)}–{_print_number(high)}{unit}: "
        f"{len(qualifying)} distinct devices in the returned inventory.**",
        "Qualifying returned device IDs: "
        + (", ".join(f"{ident} ({_print_number(value)}{unit})"
                     for ident, value in qualifying) or "none") + ".",
        f"Coverage: {len(ids)} unique device IDs from {len(pages)} original "
        f"read-only inventory page(s); source-reported total {total}.",
        f"Missing {field} values among returned IDs: {missing}; "
        f"present but nonnumeric: {nonnumeric}.",
    ]
    if complete:
        lines.append("The returned offset pages cover the source-reported inventory count.")
    else:
        lines.append(f"Not a complete inventory: {unseen} source-reported row "
                     "position(s) were not returned or reconciled. Unseen devices "
                     "may change the hub-wide count.")
    lines.append("These are stored attribute snapshots, not independently dated "
                 "measurements or proof of subsequent physical outcomes.")
    return "\n\n".join(lines)


def focused_stored_snapshot_answer(
    question: str, receipts: list[dict],
) -> str | None:
    """Safe partial if an empty read-only model answer has focused snapshots."""
    if (not isinstance(question, str)
            or not re.search(r"\b(?:current|currently|stored|snapshot)\b", question, re.I)):
        return None
    devices: dict[str, tuple[str, dict[str, str]]] = {}
    for receipt in receipts[:_MAX_RECEIPTS]:
        if not isinstance(receipt, dict) or receipt.get("name") != "hub_list_devices":
            continue
        if receipt.get("success") is not True:
            continue
        args = receipt.get("arguments")
        if (not isinstance(args, dict) or not isinstance(args.get("labelFilter"), str)
                or not args["labelFilter"].strip()):
            continue
        _, native = _response(receipt)
        if not isinstance(native, dict) or not isinstance(native.get("devices"), list):
            continue
        rows = native["devices"]
        if len(rows) != 1 or native.get("count") != 1:
            continue
        row = rows[0]
        if not isinstance(row, dict):
            continue
        ident = _safe_device_id(row.get("id"))
        label = row.get("label")
        states = row.get("currentStates")
        if (ident is None or not isinstance(label, str)
                or not _SAFE_LABEL.fullmatch(label)
                or not isinstance(states, dict)
                or args["labelFilter"].casefold() not in label.casefold()):
            continue
        selected = {}
        for field in _CURRENT_STATES:
            if field not in states:
                continue
            raw = states[field]
            numeric = _safe_number(raw)
            if numeric is not None:
                selected[field] = _print_number(numeric)
            elif isinstance(raw, str) and raw.strip().lower() in _KNOWN_STATES:
                selected[field] = raw.strip().lower()
            if len(selected) >= 8:
                break
        if not selected:
            continue
        if ident in devices and devices[ident] != (label, selected):
            return None
        devices[ident] = label, selected
        if len(devices) > _MAX_SNAPSHOT_DEVICES:
            return None
    if not devices:
        return None
    lines = [
        "**Source-only partial result — current stored hub attributes.**",
        "These values come from original focused read-only inventory receipts:",
    ]
    for ident, (label, states) in devices.items():
        lines.append(f"- **{label}** (device ID {ident}): "
                     + ", ".join(f"{name} = {value}"
                                 for name, value in states.items()) + ".")
    lines.append("No independently dated native state-event history is established "
                 "by these inventory receipts. Stored fields alone cannot "
                 "verify physical operation, continuous history, or a cause. "
                 "The model supplied no usable final text; this is a bounded "
                 "source-only fallback.")
    return "\n".join(lines)


def grouped_past_log_answer(
    question: str, receipts: list[dict],
) -> str | None:
    """Preserve original per-source returned log counts when explicitly asked."""
    if (not isinstance(question, str)
            or not re.search(r"\b(?:past[- ]logs?|log entries)\b", question, re.I)
            or not re.search(r"\b(?:by|per)\s+(?:their\s+|reported\s+)?source\b",
                             question, re.I)):
        return None
    summary = _returned_past_log_groups(receipts)
    if summary is None or "**Returned entries by reported source**" not in summary:
        return None
    return summary
