"""Source/collector evidence summaries without converting reception to event time.

Collector-only input receipts may be compared with collector copies of device
switch reports on the same collector clock. They remain *reception* ordering:
distinct stream delivery paths and missing coverage mean no causal issuer is
inferred. Do not calibrate sensor origin times with light transport delays.
"""
from __future__ import annotations

from datetime import datetime, timezone
from statistics import median
from typing import Any, Mapping, Sequence


def _when(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError):
        return None
    return value.astimezone(timezone.utc) if value.tzinfo else None


def _state(v: Any) -> str:
    value = str(v or "").lower()
    if value in {"on", "active", "present", "occupied", "true"}:
        return "on"
    if value in {"off", "inactive", "not present", "unoccupied", "false"}:
        return "off"
    return ""


def _range(values: list[float]) -> dict[str, float] | None:
    return ({"min": round(min(values), 3), "max": round(max(values), 3),
             "median": round(median(values), 3)} if values else None)


def analyse_collector_reception(
    ledger: Sequence[Mapping[str, Any]],
    input_receipts: Sequence[Mapping[str, Any]],
    *,
    truncated_inputs: Sequence[str] = (),
    input_returned_counts: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Compare exact receipt order in one collection stream, not source order.

    Samples covering only part of their returned archive page are ineligible
    for *complete pairing*; never infer absence of other sensor changes.
    A one-to-one match is a discriminatory lead, not a p-value or causation.
    """
    rows = [r for r in ledger[:200] if isinstance(r, Mapping)]
    by_target: dict[str, list[Mapping[str, Any]]] = {}
    source: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        ident = str(row.get("device_id") or "")
        kind = str(row.get("event_class") or "")
        if kind in {"journal_received_switch_on", "journal_received_switch_off"} and _when(row.get("date")):
            by_target.setdefault(ident, []).append(row)
        if kind in {"journal_source_switch_on", "journal_source_switch_off"} and _when(row.get("date")):
            source.setdefault(ident, []).append(row)
    if not by_target:
        return {"schema": "collector-reception-evidence.v1",
                "candidates": [], "light_pair": None, "light_reception_lag": None}
    # The longest fully source-qualified receiver stream becomes a reference.
    # Stable IDs break ties, never hard-coded device labels.
    valid_ids = [k for k in by_target if len(by_target[k]) >= 4 and k in source]
    if not valid_ids:
        return {"schema": "collector-reception-evidence.v1",
                "candidates": [], "light_pair": None, "light_reception_lag": None}
    primary = sorted(valid_ids, key=lambda k: (-len(by_target[k]), k))[0]
    states = sorted(by_target[primary], key=lambda r: _when(r["date"]))
    lag: list[float] = []
    for state in states:
        eligible = [(_when(state["date"]) - _when(s["date"])).total_seconds()
                    for s in source[primary]
                    if _state(s.get("value")) == _state(state.get("value"))
                    and 0 <= (_when(state["date"]) - _when(s["date"])).total_seconds() <= 4]
        if eligible:
            lag.append(min(eligible))
    candidates = []
    inputs: dict[str, list[Mapping[str, Any]]] = {}
    for row in input_receipts[:200]:
        ident = str(row.get("device_id") or "")
        if ident and _when(row.get("received_at")) and _state(row.get("value")):
            inputs.setdefault(ident, []).append(row)
    truncated = set(str(x) for x in truncated_inputs)
    for ident, input_rows in sorted(inputs.items()):
        samples = sorted(input_rows, key=lambda r: _when(r["received_at"]))
        complete = (ident not in truncated
                    and input_returned_counts is not None
                    and input_returned_counts.get(ident) == len(samples))
        if not complete:
            continue
        used: set[int] = set()
        matches: dict[str, list[float]] = {"on": [], "off": []}
        for state in states:
            state_kind = _state(state.get("value"))
            max_delay = 3.0 if state_kind == "on" else 20.0
            candidates_at = [
                (( _when(state["date"]) - _when(row["received_at"])).total_seconds(), i)
                for i, row in enumerate(samples)
                if i not in used and _state(row.get("value")) == state_kind
                and 0 <= (_when(state["date"]) - _when(row["received_at"])).total_seconds() <= max_delay
            ]
            if candidates_at:
                delay, chosen = min(candidates_at)
                matches[state_kind].append(delay)
                used.add(chosen)
        on_count = sum(_state(row.get("value")) == "on" for row in states)
        off_count = sum(_state(row.get("value")) == "off" for row in states)
        on_matched, off_matched = len(matches["on"]), len(matches["off"])
        complete_pairing = (on_count >= 3 and off_count >= 3 and
                            on_count == on_matched and off_count == off_matched
                            and len(samples) == len(used))
        candidates.append({
            "input_id": ident, "target_id": primary,
            "input_returned_rows": len(samples),
            "target_on_rows": on_count, "target_off_rows": off_count,
            "matched_on": on_matched, "matched_off": off_matched,
            "on_receiver_delay_seconds": _range(matches["on"]),
            "off_receiver_delay_seconds": _range(matches["off"]),
            "one_to_one_within_windows": complete_pairing,
            "receiver_clock_only": True,
            "sensor_source_order_verified": False,
            "initiator_verified": False,
        })
    candidates.sort(key=lambda c: (
        -int(c["one_to_one_within_windows"]), -(c["matched_on"] + c["matched_off"]),
        c["input_id"]))
    light_pair = None
    if len(valid_ids) >= 2:
        secondary = next((k for k in sorted(valid_ids) if k != primary), None)
        if secondary:
            a = sorted(source[primary], key=lambda r: _when(r["date"]))
            b = sorted(source[secondary], key=lambda r: _when(r["date"]))
            if len(a) == len(b) and len(a) >= 4 and all(
                _state(x.get("value")) == _state(y.get("value"))
                and 0 <= (_when(y["date"]) - _when(x["date"])).total_seconds() <= 2
                for x, y in zip(a, b)
            ):
                light_pair = {
                    "first_id": primary, "second_id": secondary,
                    "paired_transitions": len(a),
                    "source_event_stagger_seconds": _range([
                        (_when(y["date"]) - _when(x["date"])).total_seconds()
                        for x, y in zip(a, b)]),
                    "shared_issuer_verified": False,
                }
    return {
        "schema": "collector-reception-evidence.v1",
        "candidates": candidates[:8],
        "light_pair": light_pair,
        "light_reception_lag": _range(lag) if len(lag) == len(states) else None,
    }


__all__ = ["analyse_collector_reception"]
