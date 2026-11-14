"""Bounded original-event timeline/completeness navigation for the final audit.

Reuses successful in-request native MCP device-event receipts. No native reads,
provider rounds, write actions or answer rewriting. Timestamps/short scalar
values below are SOURCE DATA, not independent verification or causal proof.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import re

from temporal_receipt_fidelity import _native_payload, _safe_event

_MAX_RECEIPTS = 16
_MAX_SOURCE_EVENTS_PER_RECEIPT = 600
_MAX_SELECTED_FIELDS = 4
_MAX_EVENTS_PER_FIELD = 14
_MAX_COMMAND_EVENTS = 8
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_SENSITIVE = re.compile(
    r"passw|secret|token|credential|auth|pin|code|api.key|access.key|lock.code",
    re.IGNORECASE,
)


def _safe_name(name: object) -> bool:
    return isinstance(name, str) and bool(_NAME.fullmatch(name)) and not _SENSITIVE.search(name)


def _dt(row: dict) -> datetime | None:
    try:
        stamp = str(row["event_date_as_returned"])
        dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo is not None else None
    except (ValueError, TypeError, KeyError, OverflowError):
        return None


def _preview(rows: list[dict], cap: int) -> list[dict]:
    if len(rows) <= cap:
        return rows
    keep_start = cap // 2
    return rows[:keep_start] + rows[-(cap - keep_start):]


def _quoted_field(name: str, draft: str) -> bool:
    """A verbatim original field mention, not an invented synonym/target."""
    return bool(re.search(
        r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])",
        draft, flags=re.IGNORECASE,
    ))


def original_event_completeness_index(receipts: list[dict], draft: str) -> dict | None:
    """Index matching observed event fields and *all safely seen* command rows.

    A command row is not a demonstrated cause. A missing command outside the
    scanned/returned row subset is NEVER proven absent.
    """
    if not isinstance(draft, str) or not draft.strip():
        return None
    out = []
    for pos, receipt in enumerate(receipts[:_MAX_RECEIPTS], 1):
        if (not isinstance(receipt, dict)
                or receipt.get("success") is not True
                or receipt.get("name") != "hub_list_device_events"):
            continue
        original = _native_payload(receipt)
        if not isinstance(original, dict):
            continue
        rows = original.get("events")
        if not isinstance(rows, list):
            continue
        scoped = []
        for raw in rows[:_MAX_SOURCE_EVENTS_PER_RECEIPT]:
            if not isinstance(raw, dict) or not _safe_name(raw.get("name")):
                continue
            safe = _safe_event(raw, pos)
            if safe is None or _dt(safe) is None:
                continue
            scoped.append((safe, raw))
        # Source rows may arrive latest-first: never narrate list order as chronology.
        scoped.sort(key=lambda pair: _dt(pair[0]))
        grouped: dict[str, list[dict]] = {}
        commands = []
        for safe, raw in scoped:
            name = safe["event_name"]
            grouped.setdefault(name, []).append(safe)
            if raw.get("type") == "command" or name.startswith("command-"):
                command = {
                    "event_date_as_returned": safe["event_date_as_returned"],
                    "event_name": name,
                    "report_type": "original_returned_command_row",
                }
                issuer = raw.get("producedBy")
                if isinstance(issuer, dict):
                    app_id = issuer.get("appId")
                    if (type(app_id) is int and 0 < app_id < 1000000000
                            or isinstance(app_id, str) and app_id.isascii()
                            and app_id.isdecimal() and 0 < len(app_id) <= 9):
                        command["recorded_issuer_app_id"] = int(app_id)
                commands.append(command)
        matches = [(draft.lower().find(name.lower()), name)
                   for name in grouped if _quoted_field(name, draft)]
        matches.sort(key=lambda item: (item[0], item[1]))
        selected = []
        for _, name in matches[:_MAX_SELECTED_FIELDS]:
            observations = grouped[name]
            times = [_dt(v) for v in observations]
            gaps = [
                round((times[i] - times[i - 1]).total_seconds(), 3)
                for i in range(1, len(times))
            ]
            selected.append({
                "event_name": name,
                "original_returned_rows_for_name": len(observations),
                "earliest_returned_event": observations[0]["event_date_as_returned"],
                "latest_returned_event": observations[-1]["event_date_as_returned"],
                "inter_observation_gaps_seconds": gaps[:_MAX_EVENTS_PER_FIELD - 1],
                "gaps_omitted_due_to_cap": max(0, len(gaps) - (_MAX_EVENTS_PER_FIELD - 1)),
                "chronological_rows_preview": [
                    {
                        "event_date_as_returned": row["event_date_as_returned"],
                        **({"event_value": row["event_value"]}
                           if "event_value" in row else {}),
                    }
                    for row in _preview(observations, _MAX_EVENTS_PER_FIELD)
                ],
                "rows_not_in_preview": max(0, len(observations) - _MAX_EVENTS_PER_FIELD),
            })
        if not selected and not commands:
            continue
        out.append({
            "receipt_number": pos,
            "source_scope": "this one successful, originally returned native device-event result",
            "original_event_rows_in_payload": len(rows),
            "event_rows_scanned": min(len(rows), _MAX_SOURCE_EVENTS_PER_RECEIPT),
            "event_rows_not_scanned": max(0, len(rows) - _MAX_SOURCE_EVENTS_PER_RECEIPT),
            "requested_name_timelines": selected,
            "additional_mentioned_event_names_not_indexed": max(0, len(matches) - _MAX_SELECTED_FIELDS),
            "material_original_command_rows": _preview(commands, _MAX_COMMAND_EVENTS),
            "command_rows_not_in_preview": max(0, len(commands) - _MAX_COMMAND_EVENTS),
            "command_issuer_not_proof_of_internal_reason": True,
        })
    if not out:
        return None
    return {
        "purpose": (
            "Check draft counts, cited observation times, returned cadence, and "
            "material command rows against ORIGINAL receipts. Do not call a "
            "preview a full history or assume commands caused later state. "
            "No returned rows means no matching rows in this result, NOT an "
            "absence of unreturned history."
        ),
        "source_histories": out,
        "source_histories_not_examined_due_to_cap": max(0, len(receipts) - _MAX_RECEIPTS),
    }
