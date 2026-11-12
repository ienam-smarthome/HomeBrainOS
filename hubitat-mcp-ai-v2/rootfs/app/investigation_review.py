"""Model-led evidence-sufficiency checkpoint for causal and historical answers.

The checkpoint does NOT inspect data, infer a cause, select a tool, execute a
read, or rewrite an answer. It gives the connected model one final opportunity
to decide whether discriminating evidence is available before it stops.
"""
from __future__ import annotations

import re
import json

_CAUSAL_QUESTION = re.compile(
    r"\bwhy\b|\bwhat\s+(?:caused|triggered|initiated|made|explains)\b"
    r"|\b(?:cause|reason|trigger)\s+(?:of|for|behind)\b"
    r"|\bwho\s+(?:turned|switched|set|changed|started|stopped|issued)\b"
    r"|\b(?:was|were|is|are|been)\s+caused\s+by\b",
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
_VERIFICATION_REQUEST_AT_START = re.compile(
    r"^\s*(?:verify|validate|audit|confirm|establish)\b",
    re.IGNORECASE,
)
_INSPECTION_REQUEST_AT_START = re.compile(
    r"^\s*(?:inspect|investigate)\b", re.IGNORECASE,
)
_EXPLICIT_PROOF_REQUEST = re.compile(
    r"\b(?:verify|verified|independently|evidence|proof|source|provenance)\b",
    re.IGNORECASE,
)
# General evidence-verification intent, without identifying devices or tools.
_VERIFICATION_SUBJECT = re.compile(
    r"\b(?:status|state|configuration|settings|triggers?|actions?|"
    r"history|events?|readings?|measurements?|sources?|evidence|"
    r"identity|type|parent|health|flags?|service|logs?|device|rule|controller|automation)\b",
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
Honor the user's evidence conditions BEFORE concluding or calculating. If a
duration is requested ONLY when two transitions are confirmed by fresh
timestamped observations, saved-but-freshness-unknown bins do not satisfy
that condition; you may give a clearly labelled bin-time difference as
context but NOT a verified physical transition duration. Do not infer
continuous state between samples merely from a fully populated bin grid.
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


VERIFICATION_REVIEW_PROMPT = """Source-to-claim verification checkpoint (internal).
Your preceding answer is a draft, not an independent source. Compare EACH
requested factual property or user-specified proof condition against the
ORIGINAL returned receipts. Distinguish:
- directly returned typed state or event fields from a displayed UI control,
  a different property, cached snapshot, or inferred state;
- current configuration from historical configuration or actual execution;
- a stored ID pointer from independently read identity;
- reported events and recorded command issuers from internal decisions;
- actual returned history boundaries and caps from complete coverage.

A button that offers an action is not a typed status observation. An absent
field is UNKNOWN, not a negative value. One status flag does not establish
another status property. A UI configuration page alone does not prove an
event-specific execution. When the user requires verified evidence, do not
promote compatible indirect evidence into the requested direct proof.

If one proportionate READ-ONLY source may resolve a material requested
property, independently choose its actual tool and arguments now. Never
use UI controls, mutating tools or speculative actions to probe status.
There is no mandated tool or fixed read sequence; you can finish without
more tools when the evidence is already adequate or no useful read is
available. Preserve supported facts, label remaining unknowns precisely,
and disclose material row caps and unobserved intervals. Do not perform
actions, manufacture evidence, rewrite a past receipt or mention this
internal checkpoint.
"""



ACTION_OUTCOME_REVIEW_PROMPT = """Action/outcome source review (internal to this answer).
The user's requested REAL-WORLD outcome is the specification, not the
model's earlier plan or a similarly named device. Review the ORIGINAL native
tool calls and responses: what exact tool was submitted, which entity/ID and
command were affected, what the server explicitly accepted or rejected, and
what was independently observed afterward. Do NOT assume that a successful
command on one device triggers a different target's action or a future timer.

Separate (1) command sent, (2) server/driver acceptance, (3) changed target
state or stored schedule read back, and (4) future downstream execution.
Inspect ALL verification outcomes embedded in the original MCP reply, not
just its top-level success. If an optional waitFor says converged=false or
timedOut=true, DISCLOSE that attempted check's failure and compare its
expected value with the returned value even when the command succeeded and
another state supports a different postcondition. Conversely, a failed
waitFor alone does not prove command failure. Treat client_native_wait_for_scope
as a pointer into original server fields, NOT independent evidence.
Compare the requested time semantics with the executed command: "after N"
means DELAYED onset; "for N" usually means IMMEDIATE onset with a bounded
duration; "until" and "every" differ again. Do not rephrase an immediate
allow/disable command into a future delayed action. Verify actual timing
from driver semantics or original observations, not names alone. If the
available command cannot implement the user-requested timing, say so;
never execute an alternative write during this read-only review.
A virtual flag, helper object, dashboard control, linked label, or automation
proposal does not itself establish another device's action. A requested delay
is not satisfied by an unrelated immediate state change. A pending scheduled
action can only be called verified if a source supports its target and deadline;
execution at that future time remains unknown until observed. This assistant
will NOT independently wake up in the future to issue another command.

If a proportionate READ-ONLY native tool can verify the intended target,
pending schedule, relevant dependency, or reported outcome, independently
choose its actual tool and arguments now. Do not assume that a returned
snapshot is fresh or that empty, filtered queries exclude every possible
controller. A previous command or side effect must NOT be retried, undone,
replaced by another write, or treated as authorized by this review.
If sufficient evidence is already present, answer now. Otherwise report
the exact action/receipt and what remains UNVERIFIED; do not promise a later
chat-initiated action or manufacture a success confirmation. Do not mention
this internal checkpoint.
"""




CAPABILITY_DISCOVERY_REVIEW_PROMPT = """Capability/control-surface source review (internal).
The user's desired EFFECT, named physical target, and timing are separate
questions from which Hubitat device/integration implements the effect.
Review the original returned tool receipts before declaring an operation
unsupported or requiring an automation. Did you inspect just a media,
sensor, thermostat, virtual helper, or app endpoint rather than the
controller of the requested effect? Different device records may represent
the SAME physical target while exposing different controls. Do not equate
the absence of one capability on one matched record with the absence of a
separate actuator or rule. An on/off command for media or power is NOT
evidence of internet, water, heating or other unrelated effect.

Consider the REAL scope of earlier inventory queries. A labelFilter,
roomFilter, capabilityFilter, returned subset or count below unfilteredTotal
is NOT a complete inventory of action controllers. If a broader inventory
read, cross-integration device relationship, alternate control name, or
recorded prior source could resolve the mismatch, independently choose
proportionate READ-ONLY tools from the actual available catalog. Prefer
the already-offered native list/get/read tools and inspect the advertised
commands of any candidate. Shared network ID, IP, hardware label, location
or other identifier is only a candidate relationship: verify that the
controller really targets the intended physical entity before any write.
Do not conclude a direct operation exists merely from a similar label,
or infer that a model guessed the correct controller.

Check the timing and operation semantics against each ACTUAL candidate
command. A delayed start is distinct from an immediate temporary state.
If another controller exists but cannot provide the requested timing,
state precisely which part is supported and what is unverified. If you
cannot identify a matching controller, describe the search scope and
remaining unknowns rather than claiming no controller exists anywhere.

This review is strictly READ-ONLY. Do not dispatch a first or corrective
write, create a rule or proxy, auto-select another device without identity
evidence, retry or change permissions. The model chooses tools and the
final source-bounded conclusion; this checkpoint does not itself search,
schedule or grant authorization. Do not mention the internal checkpoint.
"""



# This is a separate final model pass, AFTER any model-selected evidence reads.
# It does not select tools, parse claims, rewrite text mechanically or decide
# the answer. The model compares its own final wording against original receipts.
FINAL_CLAIM_AUDIT_PROMPT = """Final source-to-claim contradiction audit (internal).
You are revising your own proposed answer, not collecting new evidence.
The original successful tool receipts are the evidence; your previous drafts,
client-side evidence indexes, and source metadata are NOT independent sources.

Before finalising, scrutinise EACH material definite statement, including
negatives ("no", "none", "did not", "not recorded", "never", "absent"),
universal claims ("all", "every"), and causal claims ("caused",
"initiated", "external", "verified"). For each such claim, locate the
ORIGINAL receipt that supports it and compare the exact scope:
entity, event/attribute filter, text pattern, lookback start/end,
returned rows, row cap, source store, freshness and reporter/issuer role.
If the original receipt does not cover the claim, narrow the statement.

Apply a counterexample check: could the missing event/command/value exist
outside the returned rows, within a gap or outside the filter, while
ALL successful receipts remain unchanged? If yes, do not say the system
recorded no such event, the action did not happen, or the history is empty.
Instead name the queried source and scope alongside the negative finding
(e.g. no matching rows RETURNED by a specified query), then state what
remains unknown. A text-pattern log search with matched=0 only excludes
matches to that pattern in that returned interval, not other app logs.
Do not let the FINAL conclusion silently broaden the evidence scope after
a correctly qualified explanation.

An accompanying bounded receipt scope index may list call arguments,
returned counts and source-derived limits. It is a NAVIGATION aid, not
independent proof or a substitute for the original successful receipts.
Read any conflicts against the original source and report uncertainty.
Preserve positive findings, including verified issuers and direct readings.

For causal questions, distinguish (a) a recorded state change,
(b) the device/bridge reporting it, (c) a recorded command issuer if present,
and (d) the internal decision or trigger that may remain unknown.
A physical-tagged state report is NOT proof of an external/manual initiator;
a filtered event list or empty named-text log search is NOT proof the hub
issued no command. A currently configured automation cannot, without
execution evidence, be either established or excluded as the event cause.
Keep positive evidence such as a real command-off issuer, with its timestamp,
even when the internal controller decision cannot be proven.

For measurements, a missing matching saved sample is NOT proof a physical
excursion did not occur. Freshness-unknown bins and current snapshots are
not source-timestamped physical observations. For status/configuration, a
stored pointer or UI button is not independently verified identity/state.
For all domains, retain relevant positive facts and original uncertainty.

There are NO tools in this final writing pass. Do not claim to have checked
additional records. If evidence is insufficient, say which fact is unknown
and why, while answering useful verified parts of the question. Produce ONLY
the final user-facing answer, with no internal audit commentary. Never
execute actions or reveal credentials.
"""


# This bounded index does not infer causation, classify claims or alter answers.
# It only re-exposes the *already returned and redacted* request scope and
# selected source-provided counts near the final model audit. Original receipts
# remain the authority, including any fields not included in this index.
_AUDIT_REQUEST_FIELDS = frozenset((
    "tool", "args", "deviceId", "appId", "attribute", "since", "until",
    "hoursBack", "limit", "pattern", "level", "mode", "metric", "range",
    "start", "end", "pageName", "offset", "max_chars", "labelFilter",
))
_AUDIT_SOURCE_FIELDS = frozenset((
    "source_kind", "returned_row_count", "requested_row_limit",
    "row_limit_reached", "requested_attribute_filter",
    "oldest_returned_event", "newest_returned_event",
    "observed_command_row_count", "unseen_rows_or_commands_proven_absent",
    "source_scope", "can_infer_unseen_commands_absent",
    "can_infer_requested_window_fully_covered",
    "can_infer_external_or_manual_initiation_from_physical_tag",
    "parent_app_identity_independently_verified",
    "fresh_sensor_reports_independently_verified",
))
_AUDIT_ORIGINAL_FIELDS = frozenset((
    "count", "matched", "total", "attributeFilter", "sinceTimestamp",
    "untilTimestamp", "hoursBack", "hasMore", "limit", "mode",
))
_AUDIT_INDEX_LIMIT = 16


def _audit_scalars(data: object, allowed: frozenset[str]) -> dict:
    if not isinstance(data, dict):
        return {}
    return {
        key: value[:120] if isinstance(value, str) else value
        for key, value in data.items()
        if key in allowed and (value is None or type(value) in (str, int, float, bool))
    }


def _audit_request(arguments: object) -> dict:
    """Include only ordinary read-scope arguments, never tokens or payloads."""
    if not isinstance(arguments, dict):
        return {}
    scoped = _audit_scalars(arguments, _AUDIT_REQUEST_FIELDS)
    if isinstance(arguments.get("args"), dict):
        scoped["args"] = _audit_scalars(arguments["args"], _AUDIT_REQUEST_FIELDS)
    return scoped


def final_claim_receipt_scope_index(receipts: list[dict]) -> str:
    """Index successful original tool receipt scopes, without causal inference.

    No source strings, logs, individual samples, passwords, or full returned
    documents are copied. A malformed/oversized receipt stays unindexed.
    """
    rows = []
    for position, record in enumerate(receipts[:_AUDIT_INDEX_LIMIT], start=1):
        if not isinstance(record, dict):
            continue
        item: dict = {
            "receipt_number": position,
            "tool": str(record.get("name", ""))[:100],
            "success": record.get("success") is True,
            "arguments": _audit_request(record.get("arguments")),
        }
        if record.get("success") is not True:
            item["read_failed"] = True
            rows.append(item)
            continue
        if record.get("operation_executed") is False:
            item["operation_executed"] = False
        try:
            parsed = json.loads(str(record.get("response", "")))
        except (TypeError, ValueError):
            rows.append(item)
            continue
        if isinstance(parsed, dict):
            head = _audit_scalars(parsed.get("client_claim_evidence_headline"),
                                  _AUDIT_SOURCE_FIELDS)
            if head:
                item["source_headline"] = head
            event_scope = _audit_scalars(parsed.get("client_event_source_scope"),
                                         _AUDIT_SOURCE_FIELDS)
            if event_scope:
                item["event_scope"] = event_scope
            monitor = parsed.get("client_monitor_evidence_scope")
            if isinstance(monitor, dict):
                mon = _audit_scalars(monitor, _AUDIT_SOURCE_FIELDS)
                if isinstance(monitor.get("history"), dict):
                    mon["history"] = _audit_scalars(
                        monitor["history"], _AUDIT_SOURCE_FIELDS)
                if mon:
                    item["monitor_scope"] = mon
            original = parsed
            content = parsed.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        try:
                            original = json.loads(str(part.get("text", "")))
                        except (ValueError, TypeError):
                            pass
                        break
            native = _audit_scalars(original, _AUDIT_ORIGINAL_FIELDS)
            if native:
                item["original_returned_fields"] = native
        rows.append(item)
    return json.dumps({
        "note": "Navigation index from returned receipt fields ONLY; not independent evidence. Do not infer unseen records absent. Inspect original receipts for full detail.",
        "indexed_receipts": rows,
        "additional_receipts_not_indexed": max(0, len(receipts) - _AUDIT_INDEX_LIMIT),
    }, separators=(",", ":"), ensure_ascii=False)


FINAL_CLAIM_AUDIT_MIN_SECONDS = 12.0


def should_audit_completion(
    *, source_review_invoked: bool, already_audited: bool,
    remaining_seconds: float, has_draft: bool,
) -> bool:
    """Allow one final model-led textual contradiction pass when time permits."""
    return (
        source_review_invoked and not already_audited and has_draft
        and remaining_seconds > FINAL_CLAIM_AUDIT_MIN_SECONDS
    )


def is_source_verification_question(question: str) -> bool:
    """Broad inspect/verification questions, independent of named devices."""
    return (
        isinstance(question, str)
        and not bool(_WRITE_INTENT_AT_START.search(question))
        and bool(_VERIFICATION_SUBJECT.search(question))
        and (
            bool(_VERIFICATION_REQUEST_AT_START.search(question))
            or bool(_INSPECTION_REQUEST_AT_START.search(question))
            and bool(_EXPLICIT_PROOF_REQUEST.search(question))
        )
    )


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
    if is_source_verification_question(question):
        return "source_verification"
    return None



# Frozen-receipt evaluation can inspect a wider range of *read-only* questions
# than the live agent's optional review trigger. Keep this heuristic out of
# review_kind(), so normal Ask does not add latency or change tool behaviour.
_FROZEN_INVENTORY_START = re.compile(
    r"^\s*(?:which|what|list|show|identify|find|compare)\b", re.IGNORECASE,
)
_FROZEN_INVENTORY_SUBJECT = re.compile(
    r"\b(?:devices?|sensors?|rules?|apps?|automations?|attributes?|"
    r"readings?|measurements?|statuses?|states?|health|settings?|"
    r"events?|logs?|sources?|values?|batteries|battery|power|memory)\b",
    re.IGNORECASE,
)


def frozen_review_kind(question: str) -> str | None:
    """Extra read-only inventory eligibility only for optional frozen replay.

    This determines a review prompt category, not factual correctness.
    It never changes production review triggers or executes tools.
    """
    kind = review_kind(question)
    if kind is not None:
        return kind
    if (not isinstance(question, str)
            or _WRITE_INTENT_AT_START.search(question)):
        return None
    if (_FROZEN_INVENTORY_START.search(question)
            and _FROZEN_INVENTORY_SUBJECT.search(question)):
        return "source_verification"
    return None


def review_prompt(kind: str) -> str:
    """Choose review guidance, not a tool or a computed answer."""
    if kind == "historical_measurement":
        return MEASUREMENT_REVIEW_PROMPT
    if kind == "source_verification":
        return VERIFICATION_REVIEW_PROMPT
    if kind == "action_outcome":
        return ACTION_OUTCOME_REVIEW_PROMPT
    if kind == "capability_discovery":
        return CAPABILITY_DISCOVERY_REVIEW_PROMPT
    return SOURCE_REVIEW_PROMPT



def is_read_only_review_tool(name: str) -> bool:
    """Only exposed read-only core tools/gateways and local receipt reads.

    In the Hubitat MCP skill, hub_read_* gateways are read-only and flat
    hub_get_*, hub_list_* and hub_search_* tools are informational. Manage
    gateways can be mixed read/write and are deliberately not exposed during
    this supplemental checkpoint. The original model loop is untouched.
    """
    return name in {"homebrain_read_prior_evidence", "homebrain_read_device_monitor",
                    "homebrain_inspect_mcp_catalog"} or (
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


# Review eligibility checks only the model's OWN completed draft. This is
# not a device/tool router, negative-answer validator, permission grant or
# response rewrite: only the model can decide which further read matters.
_CAPABILITY_DENIAL_DRAFT = re.compile(
    r"\b(?:cannot|can't|unable\s+to|not\s+possible|not\s+supported|"
    r"isn't\s+supported|doesn't\s+support|does\s+not\s+support|"
    r"neither\b[^.\n]{0,90}\b(?:direct|possible|implemented)|"
    r"no\s+[^.\n]{0,80}\b(?:capabilit(?:y|ies)|commands?|actuators?))",
    re.IGNORECASE,
)


def is_capability_denial_draft(draft: str) -> bool:
    """Review-worthy model denial, not proof that a capability is absent."""
    return isinstance(draft, str) and bool(_CAPABILITY_DENIAL_DRAFT.search(draft))


def should_review_completion(
    question: str, *, available_tools: bool, already_reviewed: bool,
    remaining_seconds: float, has_action_receipt: bool = False,
    draft: str = "",
) -> bool:
    """One optional model-led review when a claim may need better sources.

    A short deadline leaves the original answer intact. This helper never
    selects or executes an MCP tool, turns a denial into permission, or
    forces an additional data read.
    """
    return (
        not already_reviewed
        and available_tools
        and remaining_seconds > 8
        and (
            review_kind(question) is not None
            or has_action_receipt
            or is_capability_denial_draft(draft)
        )
    )
