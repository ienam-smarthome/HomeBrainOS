"""Conservative publication floor for read-only historical causal explanations.

This is not a causal planner, source selector or a proof engine. It only
rejects a few strong claim forms when original current-request source
categories cannot support them. Model-led findings remain untouched if
they do not make these unsupported categorical claims.
"""
from __future__ import annotations

import re
from investigation_source_ledger import _response

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
    r"only\s+(?:verifiable\s+|verified\s+|recorded\s+)?"
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
    r"switched|changed|operated)\s+because\b|"
    r"\b(?:directly|definitively|certainly)\s+(?:caused|triggered)\b|"
    r"\b(?:indicates|proves|confirms)\s+causation\b|"
    r"\b(?:is|was|therefore)\s+the\s+(?:verifiable\s+)?"
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

    for row in receipts[:_MAX_RECEIPTS]:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        name = row.get("name")
        if not isinstance(name, str):
            continue
        args = row.get("arguments")
        args = args if isinstance(args, dict) else {}
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
        if _DEFINITE_CAUSE.search(line):
            if not _UNCERTAIN.search(line):
                if not _has_event_time_execution_source(receipts):
                    return {"status": "unsafe", "reason": "controller_decision_unverified"}
    return {"status": "passed", "reason": None}
