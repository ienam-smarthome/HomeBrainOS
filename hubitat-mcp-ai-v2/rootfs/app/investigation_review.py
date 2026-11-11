"""Model-led evidence-sufficiency checkpoint for causal and historical answers.

The checkpoint does NOT inspect data, infer a cause, select a tool, execute a
read, or rewrite an answer. It gives the connected model one final opportunity
to decide whether discriminating evidence is available before it stops.
"""
from __future__ import annotations

import re

_CAUSAL_QUESTION = re.compile(
    r"\bwhy\b|\bwhat\s+(?:caused|triggered|initiated|made|explains)\b"
    r"|\b(?:cause|reason|trigger)\s+(?:of|for|behind)\b"
    r"|\bwho\s+(?:turned|switched|set|changed|started|stopped|issued)\b",
    re.IGNORECASE,
)

SOURCE_REVIEW_PROMPT = """Evidence-sufficiency checkpoint (internal to this answer).
Your previous draft is NOT evidence. Decide independently whether the
successful source receipts actually answer the user's causal question.

Distinguish an observed outcome, the actor reporting it, a recorded command
issuer, and an event-specific trigger or decision. Check actual returned
filters, lookback, result limits, chronology and competing explanations.
A filtered state history without command rows does not rule out unseen
commands. A device/bridge reporter and notified listeners do not prove
external initiation. Chronological compatibility alone does not prove cause.

If a relevant available READ-ONLY MCP source could materially distinguish
the remaining hypotheses, select its exact tool and arguments now. You own
that decision; there is no prescribed source order or required tool call.
If the existing evidence already establishes the answer, or no proportionate
useful read-only source remains, answer now, calibrating unsupported claims.
Do not request unnecessary reads, invent missing evidence, or change any
device, automation, setting, or external record. Follow the original user's
read-only or approval restrictions. Do not mention this internal checkpoint.
"""


# Broad, domain-independent historical retrieval hints. These select only
# whether a model may reconsider its first answer. They do NOT identify a
# measurement, convert units, decide whether any source is sufficient or
# select an MCP read.
_HISTORICAL_PERIOD = re.compile(
    r"\b(?:yesterday|overnight|earlier\s+today|"
    r"last\s+(?:night|evening|morning|afternoon|weekend|"
    r"hour|day|week|month|year|few\s+(?:hours|days|weeks))|"
    r"(?:past|last)\s+(?:\d+|few|several)\s*(?:minutes?|hours?|days?|weeks?|months?)|"
    r"previous\s+(?:hour|day|week|month|night)|"
    r"this\s+(?:morning|afternoon|evening|week)|"
    r"today|historical(?:ly)?|history|"
    r"\d{4}-\d{2}-\d{2})\b"
    r"|\b(?:between|from|during)\b[^\n]{0,65}"
    r"\b(?:\d{1,2}:\d{2}|\d{1,2}\s*(?:am|pm)|"
    r"yesterday|today|last\s+night)\b"
    r"|\b(?:at|around|by)\s*(?:\d{1,2}:\d{2}|\d{1,2}\s*(?:am|pm))\b",
    re.IGNORECASE,
)
_READ_INTENT = re.compile(
    r"\b(?:show|display|plot|chart|graph|list|read|report|check|find|"
    r"retrieve|summari[sz]e|compare|tell|give|what|when|which|how|"
    r"measurement|measurements|readings?|history|usage|consumption|"
    r"trend|values?|samples?|peak|average|maximum|minimum)\b",
    re.IGNORECASE,
)
_WRITE_INTENT_AT_START = re.compile(
    r"^\s*(?:turn|switch|set|update|delete|reboot|restart|"
    r"create|configure|enable|disable|start|stop)\b",
    re.IGNORECASE,
)

MEASUREMENT_REVIEW_PROMPT = """Requested-measurement fidelity checkpoint (internal to this answer).
The user's original question is the specification, not your preceding draft.
Before completing, compare the evidence with the exact requested target,
quantity/attribute, unit, historical interval, and requested statistic or
series. Identify which ORIGINAL returned rows measure that quantity in that
interval, versus different properties, today's state, commands, or indirect
proxies. Check timestamps, requested/returned filters, row limits, source
freshness, missing intervals and uncertainty. For physical quantities,
preserve dimensional distinctions (e.g. instantaneous power in W versus
cumulative energy in kWh, amperage in A, or energy-derived interval averages).
Only calculate a different quantity when the necessary data, assumptions,
time coverage, and units actually justify it; label estimates explicitly.

An empty matching history query means *no matching samples returned by that
query*, not that the underlying quantity was zero, the device inactive, or
the measurement unavailable from every other source. Do not silently
substitute a current snapshot, a different metric or inferred activity for
the requested historical measurement.

If the permitted live MCP catalog offers a proportionate READ-ONLY source
that could supply the requested data, you may independently select and
call it. The client does not choose a source or prescribe a fixed sequence.
If sufficient evidence already exists, answer with it. If no useful
read-only source exists or history remains missing, state the verified
coverage and what cannot be determined. Do not invent readings or perform
actions. Do not mention this internal checkpoint.
"""


def is_historical_measurement_question(question: str) -> bool:
    """General time-scoped data request, not a domain or device-name patch."""
    return (
        isinstance(question, str)
        and not bool(_WRITE_INTENT_AT_START.search(question))
        and bool(_HISTORICAL_PERIOD.search(question))
        and bool(_READ_INTENT.search(question))
    )


def review_kind(question: str) -> str | None:
    """Return one general reasoning goal, without prescribing MCP operations."""
    if is_causal_question(question):
        return "causal"
    if is_historical_measurement_question(question):
        return "historical_measurement"
    return None


def review_prompt(kind: str) -> str:
    """Choose review guidance, not a tool or a computed answer."""
    return MEASUREMENT_REVIEW_PROMPT if kind == "historical_measurement" else SOURCE_REVIEW_PROMPT



def is_read_only_review_tool(name: str) -> bool:
    """Only exposed read-only core tools/gateways and local receipt reads.

    In the Hubitat MCP skill, hub_read_* gateways are read-only and flat
    hub_get_*, hub_list_* and hub_search_* tools are informational. Manage
    gateways can be mixed read/write and are deliberately not exposed during
    this supplemental checkpoint. The original model loop is untouched.
    """
    return name == "homebrain_read_prior_evidence" or (
        isinstance(name, str)
        and name.startswith(("hub_read_", "hub_get_", "hub_list_", "hub_search_"))
    )


def read_only_review_catalog(tools: list[dict]) -> list[dict]:
    """Select only safe tool definitions; never execute or discover a leaf."""
    return [
        item for item in tools if isinstance(item, dict)
        and isinstance(item.get("function"), dict)
        and is_read_only_review_tool(item["function"].get("name"))
    ]


def is_causal_question(question: str) -> bool:
    """Broad intent hint, independent of a specific device or subsystem."""
    return isinstance(question, str) and bool(_CAUSAL_QUESTION.search(question))


def should_review_completion(
    question: str, *, available_tools: bool, already_reviewed: bool,
    remaining_seconds: float,
) -> bool:
    """Only open a model review when there is a chance to investigate safely.

    A short deadline leaves the original model response intact rather than
    risking a second model timeout. No MCP call is made by this helper.
    """
    return (
        not already_reviewed
        and available_tools
        and remaining_seconds > 8
        and review_kind(question) is not None
    )
