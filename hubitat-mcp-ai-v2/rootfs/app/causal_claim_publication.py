"""Conservative publication floor for read-only historical causal explanations.

This is not a causal planner, source selector or a proof engine. It only
rejects a few strong claim forms when original current-request source
categories cannot support them. Model-led findings remain untouched if
they do not make these unsupported categorical claims.
"""
from __future__ import annotations

import re
from datetime import datetime
from investigation_source_ledger import _response
from native_device_event_receipt import original_device_event_history

# These expressions target ASSERTIONS about an event or its cause, not scoped
# statements such as 'no matching rows were returned in this query'.
_DENIAL = re.compile(
    r"\b(?:did\s+not|didn't|never|was\s+not|wasn't)\s+"
    r"(?:turn\s+(?:on|off)|start|stop|activate|deactivate|occur|happen|"
    r"heat|run|operate)\b", re.I,
)
_GLOBAL_ABSENCE = re.compile(
    r"\b(?:no\s+(?:heating\s+)?(?:demand|activation|transition|"
    r"command|event)s?\s+(?:occurred|existed|from|during|at|today)|"
    r"only\s+(?:(?:one|the)\s+)?(?:verifiable\s+|verified\s+|recorded\s+)?"
    r"(?:heating\s+)?(?:activation|event|transition|cause)\b)", re.I,
)
_UNBOUNDED_COMMAND_ABSENCE = re.compile(
    r"\bno\b[^\n.]{0,90}\b(?:commands?|triggers?|activations?)\b"
    r"[^\n.]{0,90}\b(?:appear|occur|recorded|found|observed|issued)\b|"
    r"\b(?:there\s+(?:is|was)\s+)?no\s+record\s+of\s+(?:any\s+)?"
    r"[^\n.]{0,90}\b(?:turned|switch(?:ed|ing)?|start(?:ed|ing)?|"
    r"heat(?:ing)?|activat(?:ed|ion)|operat(?:ed|ion))\b|"
    r"\bno\s+(?:heating|motion|activity|activation)\s+"
    r"(?:occurred|started|happened)\b", re.I,
)

_DEFINITE_CAUSE = re.compile(
    r"\b(?:turned\s+(?:on|off)|started|stopped|activated|deactivated|"
    r"switched|changed|operated)\b[^\n.!?]{0,110}\bbecause\b|"
    r"\b(?:directly|definitively|certainly)\s+(?:caused|triggered)\b|"
    r"\b(?:indicates|proves|confirms)\s+causation\b|"
    r"\b(?:is|was)\s+(?:therefore\s+)?the\s+(?:verifiable\s+)?"
    r"(?:initiator|cause)\b|"
    r"\b(?:demand|cause|reason)\s+(?:came|originated)\s+from\b|"
    r"\b(?:the\s+)?(?:cause|reason)\s+(?:was|is)\s+"
    r"(?!(?:observed|established|unverified|unknown|uncertain|not)\b)", re.I,
)
# Only explanatory assertions, not explicitly *unverified* hypotheses or
# statements that a fact cannot be established, are eligible.
_UNCERTAIN = re.compile(
    r"\b(?:unverified|uncertain|unknown|cannot|can't|could\s+not|"
    r"not\s+(?:verified|proven|established|known)|might|may|could|"
    r"possibly|hypothesis|potential(?:ly)?|consistent\s+with|"
    r"compatible\s+with|would\s+need|not\s+enough)\b", re.I,
)
_SCOPED = re.compile(
    r"\b(?:returned\s+(?:rows|results|records|events)|"
    r"this\s+(?:query|read|source|history)|"
    r"inspected\s+(?:rows|window)|"
    r"queried\s+(?:source|window)|no\s+matching\s+rows)\b", re.I,
)
# A definite HISTORICAL decision/trigger may be phrased without "because".
# Treat these as causal assertions, not source-derived observations; e.g.
# "the controller reported a setpoint" alone is still permitted.
_EVENT_TIME_DECISION = re.compile(
    r"\b(?:this|that|it)\s+(?:satisf(?:ies|ied)|meet(?:s)?|met|"
    r"cross(?:es|ed))\b[^\n.!?]{0,125}\b(?:threshold|condition|demand)\b|"
    r"\b(?:caus(?:ed|ing)|trigger(?:ed|ing)|result(?:ed|ing)\s+in|"
    r"led\s+to)\b[^\n.!?]{0,125}\b(?:switch|turn|start|stop|run|"
    r"operat(?:e|ion)|chang(?:e|ed)|activat(?:e|ion)|heating|cooling)\b|"
    r"\bexplains?\s+why\b[^\n.!?]{0,110}\b(?:demand|"
    r"decision|trigger|activat|turn|switch|start|stop)\b|"
    r"\b(?:was|were|is|are)\s+(?:directly\s+)?(?:triggered|caused|initiated)\s+by\b",
    re.I,
)
_LOG_TOOL = re.compile(r"(?:^|_)(?:app|rule|controller)[a-z0-9_-]*(?:log|execution)(?:s|_|$)|"
                       r"(?:^|_)(?:log|execution)[a-z0-9_-]*(?:app|rule|controller)(?:s|_|$)", re.I)
_MAX_RECEIPTS = 80


def _has_event_time_execution_source(receipts: list[dict]) -> bool:
    """A successful nonempty original execution-log READ is a necessary
    *source-category* floor, not proof that its contents support a causal claim.
    A device events call with appId is NOT an app execution-log read.
    """
    def has_log_rows(data: dict, depth: int = 0) -> bool:
        # Native log payloads may be nested by mode. An arbitrary tool
        # wrapper or mere \"success\" flag is not an execution entry.
        if depth > 2:
            return False
        for key in ("logs", "entries", "lines", "records"):
            value = data.get(key)
            if isinstance(value, list) and value:
                return True
        for key in ("past", "data", "result", "modes"):
            value = data.get(key)
            if isinstance(value, dict) and has_log_rows(value, depth + 1):
                return True
        return False

    # A successful log of an unrelated app is not event-time evidence for
    # the controller behind an observed state or command. Use only producer
    # identities from successful original device event histories. A
    # triggered[] listener is not the initiating application.
    candidates: set[str] = set()
    for row in receipts[:_MAX_RECEIPTS]:
        validated = original_device_event_history(row)
        if validated is None:
            continue
        _, _, events = validated
        for event in events[:250]:
            if not isinstance(event, dict):
                continue
            producer = event.get("producedBy")
            app_id = producer.get("appId") if isinstance(producer, dict) else None
            if type(app_id) is int:
                app_id = str(app_id)
            if isinstance(app_id, str) and re.fullmatch(r"[0-9]{1,9}", app_id):
                candidates.add(app_id)
    if not candidates:
        return False

    for row in receipts[:_MAX_RECEIPTS]:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        name = row.get("name")
        if not isinstance(name, str):
            continue
        args = row.get("arguments")
        args = args if isinstance(args, dict) else {}
        app_id = args.get("appId")
        if type(app_id) is int:
            app_id = str(app_id)
        if app_id not in candidates:
            continue
        # The documented native hub_get_logs past tab is the actual
        # application runtime log. An appId on hub_list_device_events
        # means APP-EMITTED EVENTS and cannot substitute for runtime logs.
        native_past_log = (
            name == "hub_get_logs"
            and args.get("appId") is not None
            and args.get("mode", "past") == "past"
        )
        if not native_past_log and not _LOG_TOOL.search(name):
            continue
        _, native = _response(row)
        if isinstance(native, dict) and has_log_rows(native):
            return True
    return False



# Outcome types are generic across lights, HVAC, fans, contacts and switches.
# A numeric setpoint is a TARGET change, never a substitute for an output
# actually reporting a state change. This list describes source semantics,
# not specific apps, rooms or a user incident.
_REPORTED_OUTPUT_FIELDS = frozenset({
    "switch", "thermostatOperatingState", "motion", "contact", "lock",
    "presence", "valve", "alarm", "fanOperatingState", "operatingState",
    "windowShade", "door", "water", "smoke", "carbonMonoxide", "powerSource",
})
_MAX_CEILING_ROWS = 250


def causal_original_source_ceiling(receipts: list[dict]) -> dict:
    """Original-receipt minimum for an UNRESTRICTED causal answer.

    This is a sufficient-source *opportunity* check, NOT an evidence-based
    cause classifier. A command issuer is a proximal actor, not its input.
    A device reporter/listener is never the issuer. Even meeting this floor
    does not validate a particular historical decision or physical effect.

    The model is free to select further read-only evidence in existing
    reviews. If it does not, the publisher must not present a definite
    why/initiating-input conclusion from current inventories or setpoints.
    """
    by_field: dict[tuple[str, str], set[str]] = {}
    commands_on_device: set[str] = set()
    records: set[str] = set()
    command_issuer_ids: set[str] = set()
    observed_reports = 0
    valid_native_history_reads = 0
    for receipt in receipts[:_MAX_RECEIPTS]:
        result = original_device_event_history(receipt)
        if result is None:
            continue
        device_id, _, events = result
        valid_native_history_reads += 1
        for event in events[:_MAX_CEILING_ROWS]:
            if not isinstance(event, dict):
                continue
            inline_id = event.get("deviceId")
            if inline_id is not None and str(inline_id) != device_id:
                continue
            raw_date = event.get("date")
            if not isinstance(raw_date, str):
                continue
            try:
                stamp = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            except ValueError:
                continue
            if stamp.tzinfo is None:
                continue
            name = event.get("name")
            if not isinstance(name, str):
                continue
            if name.startswith("command-"):
                origin = event.get("producedBy")
                issuer_id = (origin.get("appId")
                             if isinstance(origin, dict) else None)
                if (type(issuer_id) in (int, str)
                        and re.fullmatch(r"[0-9]{1,9}", str(issuer_id))):
                    commands_on_device.add(device_id)
                    command_issuer_ids.add(str(issuer_id))
                continue
            if name not in _REPORTED_OUTPUT_FIELDS:
                continue
            value = event.get("value")
            if not isinstance(value, str) or len(value) > 64:
                continue
            observed_reports += 1
            records.add(device_id)
            by_field.setdefault((device_id, name), set()).add(value.casefold())

    multiple_states_on_same_output = {
        device_id for (device_id, _), values in by_field.items()
        if len(values) >= 2
    }
    recorded_command_with_output = bool(records & commands_on_device)
    related_execution = _has_event_time_execution_source(receipts)
    # This admits the *possibility* of a causal explanation from original
    # sources, not proof. No event-specific trigger is manufactured here.
    possible_event_time_chain = bool(
        multiple_states_on_same_output and
        (recorded_command_with_output or related_execution)
    )
    return {
        "scope": "current_request_original_successful_receipts_only",
        "native_history_read_count": valid_native_history_reads,
        "reported_categorical_output_rows": observed_reports,
        "two_distinct_reported_states_same_output": bool(
            multiple_states_on_same_output),
        "recorded_app_command_on_reported_output": recorded_command_with_output,
        "recorded_command_issuer_app_count": len(command_issuer_ids),
        "related_app_execution_source_category": related_execution,
        "minimum_source_categories_for_unrestricted_causal_prose":
            possible_event_time_chain,
        "cause_or_upstream_input_verified_by_this_index": False,
        "current_snapshot_or_setpoint_is_not_output_activation": True,
        "app_producer_or_listener_is_not_upstream_input": True,
        "native_history_not_exhaustive": True,
    }


def causal_event_time_source_scope(receipts: list[dict]) -> dict:
    """Small, source-category-only navigation index; NEVER a proof engine.

    Current snapshots and installed app configurations do not reconstruct
    event-time participant decisions. A command issuer is a proximal actor,
    not its upstream input, and a notified listener is not an issuer. This
    function cannot select an actuator/app or dispatch a read.
    """
    counts = {
        "current_device_inventory_reads": 0,
        "current_installed_app_configuration_reads": 0,
        "original_device_history_reads": 0,
        "original_command_rows": 0,
        "original_state_rows": 0,
        "command_rows_with_app_issuer": 0,
        "state_rows_with_app_producer_not_issuer": 0,
        "successful_app_scoped_past_log_reads": 0,
    }
    for receipt in receipts[:_MAX_RECEIPTS]:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        name = receipt.get("name")
        if name == "hub_list_devices":
            counts["current_device_inventory_reads"] += 1
        elif name == "hub_get_app_config":
            counts["current_installed_app_configuration_reads"] += 1
        native_history = original_device_event_history(receipt)
        if native_history is not None:
            counts["original_device_history_reads"] += 1
            for event in native_history[2][:250]:
                if not isinstance(event, dict):
                    continue
                name = event.get("name")
                if isinstance(name, str) and name.startswith("command-"):
                    counts["original_command_rows"] += 1
                    produced = event.get("producedBy")
                    if (isinstance(produced, dict)
                            and isinstance(produced.get("appId"), (str, int))
                            and re.fullmatch(r"[0-9]{1,9}", str(produced["appId"]))):
                        counts["command_rows_with_app_issuer"] += 1
                else:
                    counts["original_state_rows"] += 1
                    produced = event.get("producedBy")
                    if (isinstance(produced, dict)
                            and isinstance(produced.get("appId"), (str, int))
                            and re.fullmatch(r"[0-9]{1,9}", str(produced["appId"]))):
                        counts["state_rows_with_app_producer_not_issuer"] += 1
        if receipt.get("name") != "hub_get_logs":
            continue
        args = receipt.get("arguments")
        if not isinstance(args, dict) or args.get("mode") != "past":
            continue
        app_id = args.get("appId")
        if type(app_id) not in (int, str) or not re.fullmatch(
            r"[0-9]{1,9}", str(app_id)
        ):
            continue
        _, native = _response(receipt)
        if (isinstance(native, dict) and native.get("mode") == "past"
                and isinstance(native.get("entries"), list)
                and any(isinstance(item, dict) and item.get("type") == "app"
                        for item in native["entries"][:250])):
            counts["successful_app_scoped_past_log_reads"] += 1

    return {
        "scope": "successful_original_current_request_source_categories_only",
        **counts,
        "related_execution_source_category_present": (
            _has_event_time_execution_source(receipts)
        ),
        "causal_original_source_ceiling": causal_original_source_ceiling(receipts),
        "current_configuration_or_snapshot_not_historical_decision": True,
        "controller_or_master_output_not_necessarily_input_that_triggered_it": True,
        "state_producer_and_triggered_listeners_not_command_issuers": True,
        "command_issuer_not_upstream_trigger": True,
        "offered_or_successful_read_not_event_time_decision_proof": True,
        "unread_execution_sources_not_proven_unavailable": True,
    }


def causal_publication_floor(question: str, answer: str, receipts: list[dict]) -> dict:
    """Flag unqualified historical absence or causation missing execution proof.

    Does not rewrite text, issue reads or guess the focal device. The caller
    may preserve source-reported observations in an explicitly PARTIAL answer.
    In the absence of any event-time execution source, a temporal association,
    state report or attribute producer cannot verify a controller's decision.
    """
    if not isinstance(answer, str) or not answer.strip():
        return {"status": "not_applicable", "reason": None}
    if not isinstance(question, str) or not question.strip():
        return {"status": "not_applicable", "reason": None}

    # Evaluate complete short prose lines, not raw tool text, code/JSON or
    # headings. A qualified uncertainty is not turned into a definite denial.
    for line in re.split(r'(?<=[.!?])\s+(?=[A-Z])|\n', answer):
        line = line.strip().lstrip("> -*#0123456789. ")
        if not line or line.startswith(("|", "`", "{", "[")):
            continue
        if len(line) > 600:
            line = line[:600]
        # A table or explicit returned-rows summary can legitimately report
        # absence IN THAT BOUNDED SOURCE, not a whole-system absence.
        if (_DENIAL.search(line) or _GLOBAL_ABSENCE.search(line)
                or _UNBOUNDED_COMMAND_ABSENCE.search(line)):
            if not _UNCERTAIN.search(line) and not _SCOPED.search(line):
                return {"status": "unsafe", "reason": "unbounded_historical_absence"}
        if _DEFINITE_CAUSE.search(line) or _EVENT_TIME_DECISION.search(line):
            if not _UNCERTAIN.search(line):
                if not _has_event_time_execution_source(receipts):
                    return {"status": "unsafe", "reason": "controller_decision_unverified"}
    return {"status": "passed", "reason": None}
