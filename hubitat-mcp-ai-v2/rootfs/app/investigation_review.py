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
Preserve individually verified facts (such as a recorded command issuer and
its timestamp) even when the internal trigger, concurrent controller or
ultimate physical cause is not independently established. A partial causal
answer is more useful than hiding verified receipts behind an overall
"unresolved" label. Do not equate a configuration match with an
execution-specific callback or say that no alternatives remain without
source evidence excluding them.
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
    r"today|"
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
# Historical data-availability questions also need source sufficiency review,
# even when the user did not specify a clock-time interval.
_HISTORY_SOURCE_INVENTORY = re.compile(
    r"\b(?:history|historical|archives?|archived|recorded|saved)\b",
    re.IGNORECASE,
)
_HISTORY_INVENTORY_TARGET = re.compile(
    r"\b(?:devices?|meters?|sensors?|sources?|readings?|samples?|records?|"
    r"measurement|measurements)\b",
    re.IGNORECASE,
)
_HISTORY_INVENTORY_INTENT = re.compile(
    r"\b(?:which|what|available|list|show|identify|find|check|compare|"
    r"have|has|contain|stored)\b",
    re.IGNORECASE,
)
_WRITE_INTENT_AT_START = re.compile(
    r"^\s*(?:turn|switch|set|update|delete|reboot|restart|"
    r"create|configure|enable|disable|start|stop)\b",
    re.IGNORECASE,
)

MEASUREMENT_REVIEW_PROMPT = """Requested-measurement fidelity checkpoint (internal to this answer).
The user's original question is the specification, not your preceding draft.
Before completing, compare the evidence with the exact requested quantity/
attribute, unit, target, historical interval, and requested statistic or series. Identify which ORIGINAL returned rows measure that quantity in that
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

A device being selected for monitoring and the existence of an archive
filename do NOT establish the presence of saved samples for that device.
A file chunk with hasMore=true or partial retrieved-character coverage cannot
justify a claim about contents of unread ranges. Inspect client_file_cumulative_coverage
and original source receipts before asserting an archive is empty or complete.
Keep per-attribute event timestamps separate: an amperage or energy event
time is NOT a power event timestamp. Relative times must map into the
requested window with the source timezone and explicit offset.

When a structured measurement historian provides a SOURCE-DERIVED summary,
use its exact window_start_utc/window_end_exclusive_utc and requested metric.
Separate saved_bin_extrema from report_containing_saved_bin_extrema; the
latter is valid for power bins with a report, not continuous physical peaks.
expected_bin_positions and all_expected_bin_positions_populated describe
the time grid, NOT continuous observation. Count explicit_null_bin_rows,
absent_bin_positions, and held_from_report as distinct categories;
do not reuse a 24-hour source summary for a 12-hour question.
sensor_freshness_unverified means that freshness is UNKNOWN: neither
"every bin is stale" nor "every bin is fresh" follows. If the upstream
source cannot establish fresh readings, report saved-bin extrema only.
The client_monitor_evidence_scope, when present, is a compact index of the
same original monitor response, not independent corroboration. For threshold
questions, a difference between saved-bin timestamps may be stated AS a
saved-bin proxy, but not as verified time between physical crossings without
relevant fresh timestamped reports. A fully populated grid is not proof of
continuous sensor observations.
For a custom time window provide BOTH start and end; for relative twelve
hours the local monitor tool supports range=12h.

Source selection is an evidence-coverage decision, not a phrase-matching
decision based on whether the user named a historian. When a requested
full-period peak, minimum, threshold or trend rests only on a shorter
returned native event interval, its whole-period coverage is UNVERIFIED;
the native hoursBack argument or count below limit does not repair that gap.
A configured independent saved-measurement source can offer complementary
bins. Consider whether a proportionate READ-ONLY check there would
materially resolve an unseen interval or an apparent contradiction.
You may independently choose it; there is no mandated monitor call or tool
order. Conversely, do not call it without a reason or present it as
authoritative just because its bins are denser. Compare the same attribute,
unit and absolute window, and distinguish the native event list from saved
bins, including unknown sensor-bin freshness.
If prior source receipts or a previous answer conflict with a new result,
reconcile the differences in actual returned windows, filters and source
semantics. Do not overwrite a supported older observation with a narrower
new read, invent why the two histories differ, or use a prior assistant's
interpretation as independent proof. Do not claim you read the monitor
unless you actually called it in this investigation or inspected its
relevant original prior receipt.
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
        and (
            bool(_HISTORICAL_PERIOD.search(question))
            and bool(_READ_INTENT.search(question))
            or bool(_HISTORY_SOURCE_INVENTORY.search(question))
            and bool(_HISTORY_INVENTORY_TARGET.search(question))
            and bool(_HISTORY_INVENTORY_INTENT.search(question))
        )
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
    return name in {"homebrain_read_prior_evidence", "homebrain_read_device_monitor"} or (
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
