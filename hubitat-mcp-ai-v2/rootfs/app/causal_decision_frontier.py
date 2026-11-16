"""Original-receipt navigation for controller decisions behind observed commands.

This is NOT a causal verdict, tool plan, archived configuration, or evidence
that any unread source exists. No native side effects, source-specific routes,
or raw model/Hubitat content are generated. The model selects any further read.
"""
from __future__ import annotations

from collections import Counter
import re

from investigation_source_ledger import _response, _utc

_SAFE_APP_ID = re.compile(r"^[0-9]{1,9}$")
_SAFE_COMMAND = re.compile(r"^command-[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_MAX_COMMAND_INDEX = 6
_MAX_APP_IDS = 6


def _app_id(value: object) -> str | None:
    # Exclude bool (a subclass of int), arbitrary strings, and free text.
    if type(value) is int:
        value = str(value)
    if not isinstance(value, str) or not _SAFE_APP_ID.fullmatch(value):
        return None
    return value


def causal_controller_frontier(receipts: list[dict]) -> dict:
    """Identify *recorded command issuers* versus *unchecked app decisions*.

    Input is only in-request, originally successful MCP receipts. Parsing a
    command event does not prove its reported physical effect, its internal
    controller decision, or exclusivity within an unobserved window.
    """
    commands: list[tuple[object, dict]] = []
    command_count = 0
    without_app_identity = 0
    issuer_ids: set[str] = set()
    app_log_attempts: Counter = Counter()
    app_log_successes: Counter = Counter()
    app_other_read_successes: Counter = Counter()
    for row in receipts:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        args = row.get("arguments")
        args = args if isinstance(args, dict) else {}
        if name == "hub_list_device_events" and row.get("success") is True:
            _, native = _response(row)
            events = native.get("events") if isinstance(native, dict) else None
            if not isinstance(events, list):
                continue
            for event in events[:250]:
                if not isinstance(event, dict):
                    continue
                event_name = event.get("name")
                if not isinstance(event_name, str) or not _SAFE_COMMAND.fullmatch(event_name):
                    if event.get("type") != "command":
                        continue
                    # Unrecognized commands contribute to counts but not a
                    # fabricated normalized name or specific tool route.
                command_count += 1
                producer = event.get("producedBy")
                ident = _app_id(producer.get("appId")) if isinstance(producer, dict) else None
                if ident is None:
                    without_app_identity += 1
                    continue
                issuer_ids.add(ident)
                stamp = _utc(event.get("date"))
                if stamp is None:
                    continue
                commands.append((stamp, {
                    "observed_original_date": event["date"],
                    "issuer_app_id": ident,
                    "event_name": event_name if _SAFE_COMMAND.fullmatch(str(event_name)) else None,
                    "source_kind": "returned_device_command_row",
                    "recorded_issuer_not_controller_decision_proof": True,
                }))
        # An app-specific log response is a successful READ receipt, but its
        # presence is not proof that a given decision or trigger was observed.
        # Record both attempted and successful reads; do not count a config
        # fetch or an unrelated app's log as event-specific execution.
        app_id = _app_id(args.get("appId"))
        if app_id is None or not isinstance(name, str):
            continue
        if not name.startswith(("hub_read_", "hub_get_", "hub_list_", "hub_search_")):
            continue
        if "log" in name.lower() or "execution" in name.lower() or "trace" in name.lower():
            app_log_attempts[app_id] += 1
            if row.get("success") is True:
                app_log_successes[app_id] += 1
        elif row.get("success") is True and name != "hub_list_device_events":
            app_other_read_successes[app_id] += 1

    commands.sort(key=lambda pair: pair[0], reverse=True)
    ordered_ids = sorted(issuer_ids, key=int)[:_MAX_APP_IDS]
    any_issuer_logs_attempted = any(app_log_attempts[ident] for ident in issuer_ids)
    return {
        "scope": "current_request_original_successful_receipts_only",
        "original_device_command_rows_indexed": command_count,
        "command_rows_without_recorded_app_issuer": without_app_identity,
        "recorded_issuer_app_ids": ordered_ids,
        "recent_original_command_rows": [
            event for _, event in commands[:_MAX_COMMAND_INDEX]
        ],
        "app_scoped_execution_log_attempts_for_recorded_issuers":
            sum(app_log_attempts[ident] for ident in issuer_ids),
        "app_scoped_execution_log_successes_for_recorded_issuers":
            sum(app_log_successes[ident] for ident in issuer_ids),
        "app_scoped_other_read_successes_for_recorded_issuers":
            sum(app_other_read_successes[ident] for ident in issuer_ids),
        "command_issuer_is_not_decision_trigger": True,
        "recorded_command_is_not_independent_physical_activation": True,
        "no_app_log_read_does_not_prove_logs_unavailable": True,
        "no_app_log_read_does_not_prove_controller_reason_absent": True,
        # This is a REVIEW HINT, not proof any source exists or an
        # instruction to invoke a particular app/log/device.
        "controller_decision_source_unchecked_for_model_review": bool(
            issuer_ids and not any_issuer_logs_attempted
        ),
    }


CONTROLLER_DECISION_CHECKPOINT = """Controller-decision evidence checkpoint (read-only, general).
The ORIGINAL returned device history contains a command with a recorded
application issuer. That establishes an observed command issuer, NOT the
reason the controller chose to issue the command, the initiating input,
the exact executed branch, or independent physical operation.

For a user asking WHY, distinguish (1) report/state, (2) recorded command
and its exact issuer, (3) historical triggering input and controller
execution/decision record, and (4) physical outcome. Historical application
logs and relevant input-device event histories may discriminate these;
CURRENT settings, listener lists, old temperature readings, and physical
event tags are not proof of what ran at the command time.

Before a final answer, inspect ORIGINAL receipts and the live READ-ONLY
tool catalog. Independently decide whether a focused app-specific
execution/log read or event-time input history is actually available and
proportionate. Choose a tool through the existing model-led round ONLY if
useful. Do not enumerate unrelated rules/devices, assume log retention,
force a tool or add another model round. An app-scoped log query returning
zero rows does not exclude an unobserved execution. Preserve the exact
source chronology: an attribute report preceding a command log cannot be
rewritten as a proved command-before-report sequence.

If no relevant read is available or worthwhile, explain what the command
receipt proves and precisely which internal decision remains unverified.
Never issue a write, refresh, configuration command, or request extra
authorisation for a read-only inspection. Do not mention this checkpoint."""
