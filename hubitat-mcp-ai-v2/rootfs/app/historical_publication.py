"""Conservative publication checks for bounded original history receipts.

These checks flag a narrow set of categorical claims that exceed the source
contract. A pass does not establish that the remaining prose is correct.
"""
from __future__ import annotations

import re

from investigation_source_ledger import _response, _SAFE_FIELD, _SAFE_ID
from native_past_log_receipt import original_past_log_source

_CLAUSES = re.compile(r"\n+|(?<=[.!?;])\s+|\s+(?:but|however|yet)\s+", re.I)
_SAFE_SCOPE = re.compile(r"^[A-Za-z0-9:+._-]{1,80}$")
_COVERAGE = re.compile(
    r"\b(?:complete|full|entire|exhaustive)\s+(?:\w+[- ]?){0,4}"
    r"(?:history|coverage|interval|window|set of|week|day|period)\b"
    r"|\b(?:all|every)\s+(?:\w+[- ]?){0,4}(?:events?|entries|rows|messages|records)\b"
    r"[^.!?]{0,80}\b(?:window|interval|period|hours?|days?|week)\b"
    r"|\bno\s+(?:\w+[- ]?){0,4}(?:events?|entries|records)\s+"
    r"(?:were\s+)?(?:recorded|occurred|exist)\b",
    re.I,
)
# These assertions promote discrete reports into a source-wide claim.
_UNBOUNDED_SCOPE = re.compile(
    r"\b(?:proves?|establishes?|confirms?|shows?)\s+(?:that\s+)?"
    r"[^.!?]{0,75}\b(?:remained|stayed|continued)\b[^.!?]{0,55}"
    r"\b(?:throughout|between|entire|continuously)\b"
    r"|\b(?:remained|stayed|continued)\b[^.!?]{0,55}"
    r"\b(?:throughout|between|the\s+entire|continuously)\b"
    r"|\b(?:hub|system|store|log)\s+(?:saw|recorded|logged|contains?)\s+"
    r"(?:no|zero)\s+(?:\w+[- ]?){0,5}(?:events?|entries|records|changes)\b"
    r"|\b(?:did\s+not|never|has\s+not|have\s+not)\s+"
    r"(?:emit|generate|record|log|leave)\s+"
    r"(?:(?:any|a|an)\s+)?(?:\w+[- ]?){0,5}(?:events?|entries|records?|trace)\b"
    r"|\b(?:continuous|uninterrupted|gapless)\s+(?:logging|recording|coverage)\b"
    r"|\b(?:all[- ]time|unrestricted\s+by\s+time)\b"
    r"|\b(?:pruning|retention)\b[^.!?]{0,50}\b(?:entire|full|whole)\b",
    re.I,
)
_MECHANISM = re.compile(
    r"\b(?:is|was|are|were)\s+explained\s+by\b"
    r"|\b(?:each|every)\s+(?:\w+[- ]?){0,5}"
    r"(?:updates?|refreshes?|logs?|emits?|generates?|records?)\b"
    r"|\b(?:logs?|emits?|generates?|records?)\b[^.!?]{0,55}\b(?:each|every)\s+time\b"
    r"|\b(?:meaning|therefore|consequently)\b[^.!?]{0,90}"
    r"\b(?:does\s+not|never|always)\s+(?:generate|emit|record|report|log)\b"
    r"|\blogs?\s+(?:a\s+)?change\s+whenever\b"
    r"|\b(?:true|actual|definitive)\s+(?:reason|cause)\b",
    re.I,
)
_LIMITED = re.compile(
    r"\b(?:cannot|can't|could\s+not|does\s+not|do\s+not|did\s+not)\s+"
    r"(?:prove|establish|confirm|guarantee|show|verify|infer|determine)\b"
    r"|\b(?:cannot|can't|does\s+not|not\s+(?:prove|establish|confirm|guarantee)"
    r"|unverified|unknown)\b\s*(?:\w+\s+){0,8}"
    r"(?:prove|establish|confirm|guarantee|show|verify|infer|claim|assert|determine|coverage|"
    r"cause|reason|retention|complete|full|entire|all|every)\b"
    r"|\b(?:might|may|could|possibly)\s+(?:have\s+|be\s+)?"
    r"(?:explain|explain(?:ed)?\s+by|caus(?:e|ed)|update|refresh|emit|generate|record|"
    r"remain(?:ed)?|stay(?:ed)?|continu(?:e|ed))\b",
    re.I,
)
_MATCHES_ONLY = re.compile(
    r"\b(?:all|every)\s+(?:returned|matching|matched)\b"
    r"|\b(?:no|zero)\s+(?:matching\s+)?(?:\w+\s+){0,4}"
    r"(?:rows|events|entries|records)\s+(?:were\s+)?returned\b",
    re.I,
)


def _scoped_receipts(receipts: list[dict]) -> list[dict]:
    scopes = []
    for index, receipt in enumerate(receipts[:40], 1):
        if (not isinstance(receipt, dict) or receipt.get("success") is not True
                or receipt.get("operation_executed") is False):
            continue
        tool = receipt.get("name")
        args = receipt.get("arguments")
        if not isinstance(args, dict):
            continue
        if tool == "hub_list_device_events":
            field = "events"
            envelope, data = _response(receipt)
        elif tool == "hub_get_logs":
            parsed = original_past_log_source(receipt)
            if parsed is None:
                continue
            envelope, data, _ = parsed
            field = "entries"
        else:
            continue
        if (not isinstance(envelope, dict) or not isinstance(data, dict)
                or envelope.get("isError") is True or envelope.get("truncated") is True):
            continue
        rows = data.get(field)
        if (not isinstance(rows, list) or data.get("isError") is True
                or data.get("truncated") is True or data.get("response_too_large") is True):
            continue
        scope = {"index": index, "tool": tool, "returned": len(rows)}
        for key in ("deviceId", "appId"):
            value = args.get(key)
            if type(value) in (int, str) and _SAFE_ID.fullmatch(str(value)):
                scope[key] = str(value)
        for key in ("attribute", "level"):
            value = args.get(key)
            if isinstance(value, str) and _SAFE_FIELD.fullmatch(value):
                scope[key] = value
        for key in ("hoursBack", "limit"):
            value = args.get(key)
            if type(value) is int and value >= 0:
                scope[key] = value
        for key in ("since", "until"):
            value = args.get(key)
            if isinstance(value, str) and _SAFE_SCOPE.fullmatch(value):
                scope[key] = value
        if type(data.get("matched")) is int and data["matched"] >= 0:
            scope["matched"] = data["matched"]
        if type(data.get("total")) is int and data["total"] >= 0:
            scope["total"] = data["total"]
        scopes.append(scope)
    return scopes


def historical_publication_check(answer: str, receipts: list[dict]) -> tuple[str | None, str]:
    """Return a rejection reason and bounded original-receipt summary."""
    scopes = _scoped_receipts(receipts)
    if not scopes or not answer:
        return None, ""
    reason = None
    for clause in _CLAUSES.split(answer):
        # A scoped qualification should not carry over to another sentence.
        plain = clause.translate(str.maketrans("", "", "*_\x60"))
        if _LIMITED.search(plain):
            continue
        # Each/every in a description of rows is different from each/every
        # execution generating or refreshing telemetry.
        if _MECHANISM.search(plain):
            reason = "unverified_execution_or_reporting_mechanism"
            break
        if (_UNBOUNDED_SCOPE.search(plain)
                or (_COVERAGE.search(plain) and not _MATCHES_ONLY.search(plain))):
            reason = "unverified_history_or_retention_coverage"
            break
    if reason is None:
        return None, ""
    lines = ["**Bounded history evidence**"]
    for scope in scopes[:6]:
        filters = ", ".join(
            f"{key}={scope[key]}" for key in ("deviceId", "appId", "attribute", "level",
                                              "since", "until", "hoursBack", "limit")
            if key in scope
        )
        detail = f" ({filters})" if filters else ""
        counts = f"{scope['returned']} returned"
        if "matched" in scope:
            counts += f", {scope['matched']} reported matches"
        if "total" in scope:
            counts += f", source total {scope['total']} with scope unverified"
        lines.append(f"- Receipt {scope['index']}, `{scope['tool']}`{detail}: {counts}.")
    lines.append("These results do not establish complete retention or an event-time cause.")
    return reason, "\n".join(lines)
