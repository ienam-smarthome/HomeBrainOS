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
    # App-produced STATE reports are leads, not recorded command issuers.
    reporter_ids: set[str] = set()
    reported_app_values: list[tuple[object, dict]] = []
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
                if (not isinstance(event_name, str)
                        or not _SAFE_COMMAND.fullmatch(event_name)):
                    if event.get("type") != "command":
                        # App attribution on a returned device STATE row is
                        # not the underlying command nor a decision trace.
                        producer = event.get("producedBy")
                        reporter = (_app_id(producer.get("appId"))
                                    if isinstance(producer, dict) else None)
                        stamp = _utc(event.get("date"))
                        if (reporter is not None and stamp is not None
                                and isinstance(event_name, str)
                                and len(event_name) <= 64):
                            reporter_ids.add(reporter)
                            reported_app_values.append((stamp, {
                                "observed_original_date": event["date"],
                                "producer_app_id": reporter,
                                "reported_field": event_name,
                                "source_kind": "noncommand_device_state_producer",
                                "producer_is_not_proof_of_a_command_or_decision": True,
                            }))
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
    reported_app_values.sort(key=lambda pair: pair[0], reverse=True)
    ordered_ids = sorted(issuer_ids, key=int)[:_MAX_APP_IDS]
    ordered_reporters = sorted(reporter_ids, key=int)[:_MAX_APP_IDS]
    candidate_app_ids = issuer_ids | reporter_ids
    any_candidate_logs_attempted = any(app_log_attempts[ident]
                                       for ident in candidate_app_ids)
    return {
        "scope": "current_request_original_successful_receipts_only",
        "original_device_command_rows_indexed": command_count,
        "command_rows_without_recorded_app_issuer": without_app_identity,
        "recorded_issuer_app_ids": ordered_ids,
        "noncommand_state_producer_app_ids": ordered_reporters,
        "recent_app_produced_state_rows": [
            event for _, event in reported_app_values[:_MAX_COMMAND_INDEX]
        ],
        "producer_app_is_not_a_command_issuer": True,
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
        "app_logs_attempted_for_state_producers":
            sum(app_log_attempts[ident] for ident in reporter_ids),
        "app_logs_successes_for_state_producers":
            sum(app_log_successes[ident] for ident in reporter_ids),
        # This is a REVIEW HINT, not proof any source exists or an
        # instruction to invoke a particular app/log/device.
        "controller_decision_source_unchecked_for_model_review": bool(
            candidate_app_ids and not any_candidate_logs_attempted
        ),
    }


CONTROLLER_DECISION_CHECKPOINT = """Controller-decision evidence checkpoint (read-only, general).
The ORIGINAL returned device history may contain (a) a genuine command
row with a recorded application issuer, OR (b) an app listed as the
PRODUCER of a non-command state/attribute report. These are DIFFERENT:
a command row establishes a recorded issuer; a state producer is only a
candidate to investigate and MUST NOT be promoted into a command issuer.
Neither alone verifies the app's event-specific decision, participating
input, executed branch or independent physical outcome.

For a user asking WHY, distinguish (1) report/state, (2) recorded command
and its exact issuer, (3) historical triggering input and controller
execution/decision record, and (4) physical outcome. Historical application
logs and relevant input-device event histories may discriminate these;
CURRENT settings, listener lists, old temperature readings, and physical
event tags are not proof of what ran at the command time.

Before a final answer, inspect ORIGINAL receipts and the live READ-ONLY
tool catalog. An offered native past-log reader scoped to the candidate
application and focal time (for example, hub_get_logs with an appId and
mode=past when genuinely advertised) can be a discriminating source;
an appId-filtered hub_list_device_events call returns app-emitted EVENTS,
not that app's runtime/decision LOGS. Independently decide whether a focused
read of genuine execution/log evidence or event-time input history is actually
available and proportionate. Choose a tool through the existing model-led round ONLY if
useful. Do not enumerate unrelated rules/devices, assume log retention,
force a tool or add another model round. An app-scoped log query returning
zero rows does not exclude an unobserved execution. Preserve the exact
source chronology: an attribute report preceding a command log cannot be
rewritten as a proved command-before-report sequence.

If no relevant read is available or worthwhile, explain what the command
receipt proves and precisely which internal decision remains unverified.
Never issue a write, refresh, configuration command, or request extra
authorisation for a read-only inspection. Do not mention this checkpoint."""
