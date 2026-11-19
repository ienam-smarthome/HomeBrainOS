"""Model-led evidence-sufficiency checkpoint for causal and historical answers.

The checkpoint does NOT inspect data, infer a cause, select a tool, execute a
read, or rewrite an answer. It gives the connected model one final opportunity
to decide whether discriminating evidence is available before it stops.
"""
from __future__ import annotations

import re
import json

from temporal_receipt_fidelity import temporal_receipt_fidelity_index
from receipt_completeness_index import original_event_completeness_index
from receipt_grounding_anchors import receipt_grounding_anchors

# Light-touch eligibility for a *missing-source* checkpoint: explicit live
# measurement/state reads only, not generic knowledge questions or writes.
# This never selects a device, names an MCP tool, or fabricates a status.
_CURRENT_READ_START = re.compile(
    r"^\s*(?:what(?:'s|\s+(?:is|are))|which|show|check|read|report|"
    r"give|tell|is|are|list)\b", re.IGNORECASE,
)
_CURRENT_READ_TIME = re.compile(
    r"\b(?:current(?:ly)?|right\s+now|now|live|reported)\b",
    re.IGNORECASE,
)
_CURRENT_READ_SUBJECT = re.compile(
    r"\b(?:state|status|on|off|levels?|brightness|temperature|humidity|"
    r"power|batter(?:y|ies)|voltage|motion|active|health|readings?|"
    r"setpoint|switch|position|open|closed|devices?|lights?|"
    r"sensors?|thermostats?|valves?)\b", re.IGNORECASE,
)
_CURRENT_READ_EXAMPLE = re.compile(
    r"\b(?:example|hypothetical|tutorial|documentation|syntax|best\s+way|"
    r"optimis(?:e|ing)|optimiz(?:e|ing))\b",
    re.IGNORECASE,
)

# Only spend an additional model round when the draft itself refuses or
# defers an authorised READ. A direct answer without a tool receipt is still
# separately labelled unverified; it is not automatically retried.
_PENDING_READ_DRAFT = re.compile(
    r"\b(?:please\s+confirm|would\s+you\s+like\s+me\s+to|"
    r"need\s+to\s+(?:call|use|read|query|retrieve|fetch|check)|"
    r"can\s+I\s+(?:read|query|fetch|check|inspect)|"
    r"shall\s+I\s+(?:read|query|fetch|check))\b",
    re.IGNORECASE,
)


def is_deferred_read_draft(answer: str) -> bool:
    """Textual evidence of an unfinished read, never a tool or device router."""
    return isinstance(answer, str) and bool(_PENDING_READ_DRAFT.search(answer))


CURRENT_STATE_REVIEW_PROMPT = """Read-only live-state completion checkpoint (internal).
The user's original question asks for a CURRENT reported fact. The earlier
draft is NOT a device report, and no native MCP read has been attempted in
this Ask request. The source catalog only lists available tools; its existence
does NOT establish an individual device identity, actual state or freshness.

The user has already authorised proportionate READ-ONLY observation. Do NOT
ask permission to read. If the live offered READ-ONLY MCP tools can identify
the requested target and retrieve its reported state, independently choose
the exact currently advertised tool(s) and arguments NOW. Use only live tool
names and schemas; inspect the available catalog if you need discovery.
Do not invent an unadvertised tool, assume a similar name identifies a
device, or read an optional monitor merely because it is offered.

No tool is preselected or dispatched by this checkpoint: YOU decide the
source, quantity, and whether a suitable safe read is available. If no
proportionate supported source exists, state precisely that the requested
state is unverified. Report only returned facts, units and field-specific
timestamps; do not confuse a configured source with a successful device read.
Never change a device, rule, setting or record. Never request approval for
a read-only source. Follow the user's read-only restriction. Do not mention
this internal checkpoint.
"""


_CAUSAL_QUESTION = re.compile(
    r"\bwhy\b|\bwhat\s+(?:caused|triggered|initiated|made|explains)\b"
    r"|\b(?:cause|reason|trigger)\s+(?:of|for|behind)\b"
    r"|\bwho\s+(?:turned|switched|set|changed|started|stopped|issued)\b"
    r"|\b(?:was|were|is|are|been)\s+caused\s+by\b"
    r"|\bwhat\s+led\s+to\b",
    re.IGNORECASE,
)
# Historical outcome reconstruction and command-issuer requests are causal
# investigations even without the literal word 'why'. The model, not this
# classifier, selects the device, evidence and any follow-up tools.
_CAUSAL_RECONSTRUCTION = re.compile(
    r"^\s*(?:investigate|analyse|analyze|trace|reconstruct|explain)\b"
    r"[^.!?\n]{0,220}\b(?:transition|change|toggled|switched|turned|"
    r"stopped|started|command|issuer|automation|controller|incident)\b",
    re.IGNORECASE,
)
_CAUSAL_UNRESOLVED = re.compile(
    r"\b(?:unknown|unverified|undetermined|unresolved|uncertain|"
    r"not\s+(?:established|verified|determined|confirmed|captured|identified)|"
    r"cannot\s+(?:determine|verify|confirm|attribute|establish|identify)|"
    r"insufficient\s+(?:evidence|source|information)|"
    r"missing\s+(?:evidence|sources?|records?|logs?|link)|"
    r"(?:further|additional)\s+(?:read|source|evidence|log|investigation)|"
    r"no\s+(?:direct|decisive|clear)\s+evidence|"
    r"(?:still\s+)?(?:requires?|needs?)\s+(?:further\s+)?(?:investigation|execution\s+logs?))\b",
    re.IGNORECASE,
)

SOURCE_REVIEW_PROMPT = """Evidence-sufficiency checkpoint (internal to this answer).
Before any causal interpretation, establish the reported HISTORICAL focal
outcome from the actual controlled output/device. If the user asks WHY
something turned on, off, started or stopped, do not substitute a related
sensor/room/zone's operating-state history, a current output snapshot,
thermostatMode, historical setpoint alone or a mode/schedule change for the
controlled output's own historical switch/operating-state/command evidence.
An uninspected candidate actuator remains UNVERIFIED, not known idle.
Reconcile exactly which inventory candidates were identified and which
device IDs and output attributes were actually read. A successful read of
an unrelated device cannot support a categorical denial of the user's event.
If an appropriate currently-offered READ-ONLY source can fill this gap,
choose it proportionately during this existing review; do not scan every
inventory member or force a particular target or tool.

Your previous draft is NOT evidence. Decide independently whether the
successful source receipts actually answer the user's causal question.

Distinguish an observed outcome, the actor reporting it, a recorded command
issuer, and an event-specific trigger or decision. Reconstruct the time line
from ORIGINAL source timestamps: a previous state, the focal outcome, relevant
commands, and subsequent state. A report of a new value does not prove the
immediately previous value unless that previous value was observed. A later
current snapshot or temperature reading cannot be projected back onto the
focal event. When an apparent setpoint/state report precedes its recorded
command, preserve that order and do not invent latency or rearrange entries.
Distinguish whether the question asks about the latest event of a SPECIFIC
type versus the latest overall state, and disclose later changes.
Check actual returned filters, lookback, result limits, chronology and
competing explanations.
Before selecting another source, use the receipts ALREADY retrieved. Check
source-provided exact event-name counts for repeated command types, compare
the source-matched log count against the actual returned log entries and their
times, and inspect relevant configured selected-input groups rather than
fixating on a single participant. Return-limit and match-count differences
are evidence of bounded coverage, not missing actions or proven exclusivity.
Selected current input references are not historical trigger execution proof.
Also inspect capability inputs whose currently returned value is explicitly
null or empty. If the proposed causal explanation relies on an input that
this source reports as unselected, identify this contradiction explicitly.
Do not resolve it by assuming the input used to be selected or was inherited:
a linked page, another controller or historic settings could differ, but
must be checked or acknowledged as unknown. A timing match alone cannot
erase a conflicting configuration or turn a source failure into no evidence.
A filtered state history without command rows does not rule out unseen
commands. A device/bridge reporter and notified listeners do not prove
external initiation. Chronological compatibility alone does not prove cause.
Compare any focal event's timestamp with BOTH the source's requested history
bounds and the first/last matching rows actually RETURNED. A later oldest
returned row does not mean an earlier focal event falls outside the requested
lookback or establish that the store erased the missing samples. Where event-
time inputs are not returned, look for proportionate alternative read-only
sources or say the decisive input is unknown.
Likewise, sequential state and power telemetry are device-reported
observations, not independent confirmation of the physical mechanism.
Check intervening samples before describing a continuous drop or claiming
physical verification. Current controller settings do not establish which
historical decision path actually executed.

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
If a relevant source read FAILED (HTTP error, timeout, unsupported tool),
say which read failed and that it provides NO evidence in either direction;
do not reword a failed query into "no events found" or "logs unavailable"
without disclosing the failure. When reporting, prefer a compact sequence
and concise source-limit and uncertainty paragraphs over exhaustive prose;
do not reconstruct the same evidence in repeated tables.
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
    r"(?:past|last|previous)\s+(?:\d+|few|several|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s*(?:minutes?|hours?|days?|weeks?|months?)|"
    r"previous\s+(?:hour|day|week|month|night)|"
    r"this\s+(?:morning|afternoon|evening|week)|"
    r"today|all\s+(?:night|day|morning|afternoon|evening)|"
    r"\d{4}-\d{2}-\d{2})\b"
    r"|\b(?:between|from|during)\b[^\n]{0,65}"
    r"\b(?:\d{1,2}:\d{2}|\d{1,2}\s*(?:am|pm)|"
    r"yesterday|today|last\s+night)\b"
    r"|\b(?:at|around|by|since)\s*(?:\d{1,2}:\d{2}|\d{1,2}\s*(?:am|pm))\b"
    r"|\bsince\s+(?:yesterday|last\s+night|\d{4}-\d{2}-\d{2})\b",
    re.IGNORECASE,
)
# Strict read-intent entry for period-wide STATE questions that do not
# contain measurement verbs such as show/report and do not ask why.
# This is an eligibility hint only: it cannot select a tool or supply
# evidence of a continuous physical state.
_CONTINUITY_READ_START = re.compile(
    r"^\s*(?:did|do|does|was|were|has|have|had|is|are|"
    r"check|confirm|verify|establish|determine|investigate|"
    r"find|show|report|tell|compare|whether)\b", re.IGNORECASE,
)
_CONTINUITY_PERSISTENCE = re.compile(
    r"\b(?:remain(?:ed|ing)?|stay(?:ed|ing)?|"
    r"continu(?:ous|ously)|uninterrupted|throughout|"
    r"entire|whole|ever|all\s+(?:night|day|morning|evening)|"
    r"at\s+any\s+point|"
    r"(?:been|kept)\s+(?:on|off|active|connected|online|running|heating)|"
    r"without\s+(?:any\s+)?(?:interruptions?|changes?|outages?|"
    r"disconnections?)|any\s+(?:interruptions?|changes?|"
    r"transitions?|outages?|disconnections?|switches?|"
    r"motion|events?))\b",
    re.IGNORECASE,
)
_CONTINUITY_STATE_SUBJECT = re.compile(
    r"\b(?:on|off|active|inactive|idle|heating|cooling|running|"
    r"connected|disconnected|online|offline|powered|power|"
    r"open|closed|state|status|switch(?:ed|es)?|"
    r"devices?|sensors?|lights?|thermostats?|plugs?|"
    r"motors?|motion|temperature|humidity|energy|"
    r"interruptions?|changes?|transitions?|outages?|disconnections?)\b",
    re.IGNORECASE,
)
_CONTINUITY_FOR_PERIOD = re.compile(
    r"\bfor\s+(?:the\s+)?(?:last|past|previous)?\s*"
    r"(?:\d+|few|several|one|two|three|four|five|six|seven|"
    r"eight|nine|ten|eleven|twelve)\s*(?:minutes?|hours?|days?|weeks?)\b",
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
_CHECK_WITH_PROOF_AT_START = re.compile(
    r"^\s*check\s+(?:whether|if)\b", re.IGNORECASE,
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
    r"identity|type|parent|health|flags?|service|logs?|device|rule|controller|automation|"
    r"capabilit(?:y|ies)|support|schema|compatibility)\b",
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
A successful monitor mode=status read gives a latest/cached value and
configuration only; it is NOT a mode=history or mode=compare saved-window
read. Do not turn that timestamp into the last non-zero power reading when
its numeric value is not present; a stale power_fresh=false status is not a
fresh sensor measurement. A native 0-row event query plus status ONLY means
the historic monitor window was NOT CHECKED. It is inaccurate to say no
samples exist in both sources without an executed historical monitor read.
If a monitor history source is offered and a status receipt identifies the
target as selected, consider independently choosing a proportionate read
using the advertised tool schema and the original requested window.
Do NOT automatically read, demand additional authorisation for read-only
history, invent saved-bin values or infer historical inactivity from 0 W now.
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
A request to establish a state CONTINUOUSLY across an interval is not
equivalent to a trend of sampled power, temperature, motion or setpoints.
A positive current switch/online snapshot cannot be backdated; nonzero
historical power bins do not prove uninterrupted power, even when every
bin position is populated. Differentiate fresh report-containing bins,
carried-forward values and unobserved intervals. If historical state
transitions or connectivity/command history are already returned, compare
their actual time coverage; a source without events outside its returned
window cannot rule out interruptions there. When one proportionate
additional READ-ONLY state/transition source could materially resolve
this particular requested continuity claim, independently decide whether
to read it in this existing review stage. Do not mandate a history call,
invent a read, or declare continuity merely because a source is offered.
If no suitable source was read or the source remains bounded, say exactly
which interval or state is not verified. Report sampled observations
positively without turning missing records into a definite outage.
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

When composing the user-facing answer, lead with the direct finding and a
short explanation of relevant evidence/gaps. Do NOT turn a compact answer
into a long two-column evidence audit, put HTML <br> or JSON inside a
Markdown table, repeat a summary or enumerate raw bin fields. Keep detailed
technical source values in their original receipts. A current switch-state
snapshot cannot establish the state throughout a historic power interval;
missing saved bins cannot by themselves establish a paused telemetry stream,
and power variation alone does not prove the appliance's internal mechanism.
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

For capability or compatibility questions, distinguish server-advertised tool
and guide documentation, type/driver catalogues, a typed currently installed
instance, its precise field/action schema, an accepted configuration, and
observed runtime execution. These are different proof levels. An application
TYPE ID is not its installed INSTANCE ID; a valid variable-value format is
not evidence of a trigger's scheduling contract or its timing accuracy.
Ask for additional READ-ONLY native source evidence only if a suitable safe
source is genuinely available. If the server warns that opening/rendering a
form executes app code or can mutate state, do NOT probe it during a
read-only investigation. Do not assert an installed capability, deadline,
permission or physical effect solely from a guide or catalogue listing.

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
controller. For timed requests, compare the USER-REQUESTED local target and timezone
with the ORIGINAL source-reported stored deadline, explicitly side by side.
The client clock helper performs neutral arithmetic but reports CLIENT clock,
not an independently observed hub clock. A future deadline returned in the
write response is only a response snapshot; a separate native read AFTER the
write is needed for independent read-back. If the requested and stored times
differ beyond a justified tolerance, say the schedule DOES NOT MATCH the
request, even if the native command was accepted. Offer a user-authorised
cancel/correction path but DO NOT perform it in this read-only review.
Never imply that a future action fired or the downstream physical effect
occurred merely from a stored timer.

A previous command or side effect must NOT be retried, undone,
replaced by another write, or treated as authorized by this review.
If sufficient evidence is already present, answer now. Otherwise report
the exact action/receipt and what remains UNVERIFIED; do not promise a later
chat-initiated action or manufacture a success confirmation. Do not mention
this internal checkpoint.
"""



# This is a separate final model pass, AFTER any model-selected evidence reads.
# It does not select tools, parse claims, rewrite text mechanically or decide
# the answer. The model compares its own final wording against original receipts.
RECEIPT_GROUNDING_GUIDANCE = """Use receipt roles literally. A state reporter
emits the report. A notified app receives that event. A recorded issuer issued
only the command in its own row. Require event-time evidence to attribute a
decision or explain the cause of a state, diagnostic label or timestamp.
Use the exact source timestamp or the supplied hub display time without
applying the offset again. Preserve requested scope, returned rows and matched
rows separately. An unscoped total, a complete page of matches or a truncated
response does not establish retention. Attribute pagination and projection
to the receipts that used them. Lead with the strongest supported answer and
name the evidence gap that prevents a stronger conclusion."""

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
For every time-scoped claim, compare the focal timestamp with the ORIGINAL
requested since/until or relative-lookback start, then separately with the
oldest/newest RETURNED row. Source-declared FALSE coverage guarantees are
binding negative proof limits: an index entry that says
can_infer_uninterrupted_state_between_events=false or
can_infer_requested_window_fully_covered=false means THIS source cannot
certify whole-interval continuity/completeness. A row limit NOT reached
does not override those explicit flags, and a missing matching event name
in a mixed-attribute list is not independent evidence of no transition.
Before publishing a statement that a device stayed in one state, spell out
the positive source evidence needed to exclude alternative unseen states;
if no actually returned source establishes that, report observed transitions
and current status separately, leaving interval continuity UNVERIFIED. The first returned row is NOT the query start,
native retention boundary, or proof the requested interval was fully covered.
If the focal time is inside the query but matching rows were not returned
for that interval, describe missing returned evidence; never call the focal
time "outside the lookback" solely because the earliest returned row is later.
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

Before saying "only one" or "no other" command/event occurred, compare the
claim with EVERY relevant exact event name/count in the original returned
rows. Reconcile each draft's statement of a TOTAL NUMBER of observation
batches, events, and refreshes against every returned matching event row.
Use source timestamps for the CADENCE: do not call six observations about
30 minutes apart "four hourly refreshes". A draft may cite just selected
illustrative rows, but a claim that those are the ONLY relevant returned
observations must match ALL original rows of each named event type.
Also check EVERY returned command row that is material to the timeline,
including commands the draft omitted. Preserve command name, time and
recorded issuer while separating a command being issued from its execution
or any controller's unverified internal reason. More than one returned command of the same type disproves a claim
that only one exists IN THE WHOLE RETURNED WINDOW; it does not preclude one
specific command being closest in time to the focal outcome. Distinguish
a unique command immediately adjacent to the focal event from unique
history, no competing issuer in a bounded result, and proven exclusivity.
Never infer that no competing action could exist beyond the returned rows.

For log results, compare (1) requested since/until, (2) source-matched
entries, (3) entries ACTUALLY returned, and (4) first/last returned log
timestamps. If thousands matched but only a small capped page was returned,
do not claim to have inspected the full requested log interval or to
exclude commands in the unreturned pages. A log time without an explicit
UTC offset must not be silently converted to a verified UTC timestamp.
A hub log echo of a device state is not independent physical confirmation.
A successful monitor latest-value status read is not a historical archive
query: it cannot support a six-hour archive-empty verdict, an interval-wide
zero-power claim, or the numeric value of a last non-zero report from a
last-power-event TIMESTAMP alone. Treat monitor power_fresh=false as a
snapshot freshness limitation, not a verified stale interval. Preserve
readable UK times rather than copying raw ISO into normal prose.

For controller configuration pages, compare the actual selected input
groups, not just the one sensor or actuator named in the draft. If several
selected inputs could contribute to an internal decision, incorporate the
independently observed relevant histories or state the unchecked inputs
and conditions. Selected device labels, current app settings and UI status
text cannot prove historical input values or which callback/timer fired.
An enabled-but-unchecked backup/override/restriction input is not verified
inactive at the focal time. Event-time alignment and a recorded command
issuer are strong evidence, not proof of the controller's internal reason.
When an ORIGINAL returned device event identifies an app as the command
issuer, treat that as a useful proximate finding. For a WHY answer, check
whether event-time controller decision logs and input events were actually
read; app list, room mode, current configuration, and an older sensor value
do NOT establish the exact callback, timer, threshold, latch or hysteresis
decision for the focal command. Never claim available execution logs were
exhausted when none were attempted, or say the internal reason was verified
from an issuer row alone. Preserve the source's actual event chronology
when attribute rows precede a recorded command row. Keep the final answer
short, but explicitly distinguish observed command, app decision and
reported physical effect.
If the CURRENT configuration explicitly returns null/empty for a capability
input required by the proposed causal story, flag that as contrary or
unresolved evidence: do not confidently select that path just because its
timing matches. It may have been configured differently historically or
another controller may own the input; neither is verified until read.

An accompanying bounded receipt scope index may list call arguments,
returned counts and source-derived limits. It is a NAVIGATION aid, not
independent proof or a substitute for the original successful receipts.
Read any conflicts against the original source and report uncertainty.
Preserve positive findings, including verified issuers and direct readings.
The final audit must **correct** unsupported claims without expanding a
short user-facing answer into a raw evidence table, repeated technical
checklist, fenced JSON or HTML line-break markup. Preserve the direct
answer first, then concise source limits; leave full originals in PRIVATE
receipts. Do not claim missing saved bins prove a reporting outage or a
current switch state proves interval-long continuity.

For causal questions that ask WHY an event occurred, check the ORIGINAL
device IDs and event attributes actually read for the CONTROLLED OUTPUT,
not just connected input devices or a room/zone's current idle state.
A statement that a user-reported historical activation "did not happen",
"never occurred", "only a setpoint changed" or that the entire system
remained idle requires outcome-specific historical support. Device-specific
idle rows, repeated heat-mode reports, an unrelated mode event or a later
OFF snapshot do not exclude an unread actuator's earlier activation.
If the focal output was not historically inspected, correct any categorical
denial to a scoped UNKNOWN. Never promote a broad lack-of-records claim
from a subset of device IDs, filters or lookback windows. Do not infer an
unrecorded real-world event merely because the user reports it either.
For causal questions, distinguish (a) a recorded state change,
(b) the device/bridge reporting it, (c) a recorded command issuer if present,
and (d) the internal decision or trigger that may remain unknown.
Check the original previous-state event before calling a transition from X
to Y verified; the returned Y state alone does not establish X.
Explicitly compare requested history start/end to FIRST/LAST returned rows
and distinguish "zero matching transitions returned" from "no transitions
occurred". Do not convert either a current state or a zero count in a
partially observed event list into a verified state for an entire interval. Do not use
a temperature, level, demand, or other observation made AFTER a historical
outcome as evidence for the earlier moment. Check the latest relevant state
AFTER the focal event, rather than implying an old OFF/idle still holds.
Distinguish a device's CURRENT status from its past interval: a latest
ON/online/idle state plus sampled nonzero power/temperature/setpoint
observations cannot prove the device stayed ON/connected/heating uninterrupted
throughout. For interval-wide statements, inspect original state-transition
and coverage receipts if returned, including source-specific filters, row
caps, missing intervals and held/cached samples. If complementary state history
was not read, do not claim it was checked; keep continuity unverified and
identify the discriminating source type without demanding a new read in this
final tool-free stage.
Bind every claimed historical reading to ONE original event row's FULL date,
clock/offset, attribute name AND value. Never splice the time of one event
together with a value from another event or a later current-state snapshot.
Put the cited events in chronological order, not tool-return order, even
when source rows arrived newest-first. An approximate/derived time must be
labelled as such; a matching clock WITHOUT matching date/name/value is not
proof of a claim.

When attributing an action to a configured timeout, threshold or hysteresis,
compute the elapsed interval from the ACTUALLY OBSERVED proposed trigger to
the observed outcome, then compare it with the configured requirement.
A shorter elapsed period contradicts that specific trigger+delay explanation.
Do not invent an earlier countdown start, expedited callback or alternate
internal path to reconcile this without a returned record proving it.
Other configured sensors/conditions may remain unobserved, so the overall
initiator can still be unknown. Separate current settings from historical
settings and a listener/notification from a recorded command issuer.
A nearby timestamp or source-derived time anchor is only navigation metadata,
not independent evidence or a causal verdict.

A physical-tagged state report is NOT proof of an external/manual initiator;
a filtered event list or empty named-text log search is NOT proof the hub
issued no command. A currently configured automation cannot, without
execution evidence, be either established or excluded as the event cause.
Keep positive evidence such as a real command-off issuer, with its timestamp,
even when the internal controller decision cannot be proven.
For proposed physical outcomes, check the actual order of ALL relevant
returned state/power samples, including intervening nonzero readings. A
device-reported 0 W and a switch-off report support what the sensors
reported; they do not independently prove a physical shutdown or exclude
later/unseen activity. Never turn correlated telemetry into "physical
confirmation" or invent a monotonic power drop. Distinguish command
acceptance, reported outcome and independent physical verification.

For measurements, a missing matching saved sample is NOT proof a physical
excursion did not occur. Freshness-unknown bins and current snapshots are
not source-timestamped physical observations. For status/configuration, a
stored pointer or UI button is not independently verified identity/state.
For capability questions, separate a documented operation or app TYPE from
a verified INSTALLED instance and exact field schema. A variable format
does not establish trigger precision or runtime execution. Never claim
installed compatibility from a guide alone.
For all domains, retain relevant positive facts and original uncertainty.

A FAILED receipt is not an empty successful response. If a relevant read
failed with an HTTP error/timeout or unsupported operation, preserve its
tool identity and failure in the final answer, and state that the attempted
source does not support an affirmative or negative claim. Do not silently
remove failed-source status when revising an earlier draft. Explicitly
distinguish an unattempted source, an attempted FAILED source, and a
successful source that returned zero matching records.

Be efficient while preserving the evidence. Unless the user expressly asks
for a comprehensive report, aim for about 350–550 words: one compact focal
chronology, key positive/negative command facts, actual returned source
limits, one concise causal assessment, and the important unknowns/failures.
Avoid repeating the same tables or lengthy preparatory reasoning. Keep
exact event timestamps when available, but omit irrelevant historical
details and redundant restatements. This is an answer-writing target, not
an instruction to omit important qualifications or truncate output.

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
    "can_infer_uninterrupted_state_between_events",
    "can_infer_older_events_absent", "native_store_checked_independently",
    "can_infer_cause_of_missing_records",
    "largest_gap_between_returned_events_seconds",
    "events_returned", "requested_lookback_hours", "requested_limit",
    "limit_reached", "upstream_reported_attribute_filter",
    "date_rows_without_parseable_offset", "command_rows_in_this_response",
    "can_infer_initiator_from_state_report_producer",
    "can_infer_initiator_from_triggered_listeners",
    "can_infer_external_or_manual_initiation_from_physical_tag",
    "parent_app_identity_independently_verified",
    "fresh_sensor_reports_independently_verified",
))
_AUDIT_MONITOR_HISTORY_FIELDS = frozenset((
    # Only already-returned, source-derived scalar coverage. No raw samples,
    # log text, current-home device names, secrets or invented state intervals.
    "source_kind", "device_id", "metric", "unit", "observational_unit",
    "resolution", "requested_window_start_utc",
    "requested_window_end_exclusive_utc", "returned_window_start_utc",
    "returned_window_end_utc", "expected_bin_positions",
    "bins_with_saved_values",
    "bins_containing_monitor_received_power_reports",
    "bins_held_from_previous_power_report", "explicit_null_bin_positions",
    "absent_bin_positions", "all_saved_bin_values_present",
    "source_completeness_verified",
    "source_verified_continuous_physical_observation",
    "source_verified_device_connection_or_offline_cause",
    "source_verified_exact_physical_threshold_crossing_time",
    "fresh_sensor_reports_independently_verified",
))
_AUDIT_ORIGINAL_FIELDS = frozenset((
    "count", "matched", "total", "attributeFilter", "sinceTimestamp",
    "untilTimestamp", "hoursBack", "hasMore", "limit", "mode",
))
_AUDIT_INDEX_LIMIT = 16
_AUDIT_EVENT_GROUP_LIMIT = 20
_AUDIT_SELECTED_GROUP_LIMIT = 12
_AUDIT_SELECTED_ITEM_LIMIT = 12
_AUDIT_EMPTY_INPUT_LIMIT = 16


def _audit_event_groups(source: object) -> dict | None:
    """Re-expose exact already-returned event-name counts, never causal proof."""
    if not isinstance(source, dict):
        return None
    groups = source.get("event_names")
    if not isinstance(groups, list):
        return None
    out = []
    for row in groups[:_AUDIT_EVENT_GROUP_LIMIT]:
        if not isinstance(row, dict):
            continue
        name = row.get("event_name")
        count = row.get("returned_count")
        if isinstance(name, str) and 0 < len(name) <= 100 and type(count) is int:
            if 0 <= count <= 100000:
                out.append({"event_name": name, "returned_count": count})
    return {
        "source_scope": "exact names/counts of returned event rows only",
        "returned_event_name_counts": out,
        "event_groups_omitted": max(0, len(groups) - _AUDIT_EVENT_GROUP_LIMIT),
        "unreturned_events_proven_absent": False,
    }


def _audit_selected_inputs(source: object) -> dict | None:
    """Show the model the selected participants already in a config receipt.

    Existing config_source_map sanitises sensitive fields. Only bounded
    names/labels are re-exposed; raw settings and embedded UI markup are not.
    """
    if not isinstance(source, dict):
        return None
    groups = source.get("selected_input_groups")
    if not isinstance(groups, list):
        return None
    output = []
    for row in groups[:_AUDIT_SELECTED_GROUP_LIMIT]:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        if not isinstance(name, str) or not 0 < len(name) <= 96:
            continue
        raw = row.get("selected")
        participants = []
        if isinstance(raw, list):
            for item in raw[:_AUDIT_SELECTED_ITEM_LIMIT]:
                if not isinstance(item, dict):
                    continue
                ident, label = item.get("value"), item.get("label")
                if not isinstance(ident, str) or len(ident) > 96:
                    continue
                participants.append({
                    "value": ident,
                    **({"label": label} if isinstance(label, str)
                       and 0 < len(label) <= 120 else {}),
                })
        else:
            raw_values = row.get("selected_values")
            if isinstance(raw_values, list):
                participants = [
                    {"value": v} for v in raw_values[:_AUDIT_SELECTED_ITEM_LIMIT]
                    if isinstance(v, str) and 0 < len(v) <= 96
                ]
        returned_count = row.get("returned_selected_count")
        output.append({
            "input_group": name,
            "returned_selected_count": returned_count
            if type(returned_count) is int and 0 <= returned_count <= 100000
            else len(participants),
            "selected": participants,
            "other_selected_items_omitted": max(
                0, (returned_count if type(returned_count) is int
                    and returned_count >= 0 else len(participants))
                - len(participants),
            ),
        })
    explicitly_empty = source.get("explicitly_empty_capability_inputs")
    null_or_empty = []
    if isinstance(explicitly_empty, list):
        for row in explicitly_empty[:_AUDIT_EMPTY_INPUT_LIMIT]:
            if not isinstance(row, dict):
                continue
            name = row.get("name")
            kind = row.get("type")
            val_kind = row.get("returned_value_kind")
            if (isinstance(name, str) and 0 < len(name) <= 96
                    and isinstance(kind, str) and kind.startswith("capability.")
                    and len(kind) <= 70 and val_kind in ("null", "empty_list")):
                null_or_empty.append({
                    "input_group": name,
                    "type": kind,
                    "returned_value_kind": val_kind,
                })
    return {
        "source_scope": "one currently returned configuration page",
        "selected_input_groups": output,
        "selected_input_groups_omitted": max(
            0, len(groups) - _AUDIT_SELECTED_GROUP_LIMIT),
        "explicitly_null_or_empty_capability_inputs": null_or_empty,
        "empty_capability_inputs_omitted": max(
            0, len(explicitly_empty) - _AUDIT_EMPTY_INPUT_LIMIT)
            if isinstance(explicitly_empty, list) else 0,
        "historical_configuration_verified": False,
        "event_specific_callback_verified": False,
    }


def _audit_log_scope(source: object) -> dict | None:
    """Bounded original log-return counts/timestamps; do not read messages."""
    if not isinstance(source, dict) or not isinstance(source.get("entries"), list):
        return None
    entries = source["entries"]
    times = [
        row["time"] for row in entries
        if isinstance(row, dict)
        and isinstance(row.get("time"), str)
        and len(row["time"]) <= 45
        and row["time"][:4].isdigit()
    ]
    matched = source.get("matched")
    count = source.get("count")
    # The source-provided log times can be naive local strings. Preserve them
    # verbatim; sorting a uniform timestamp string is not timezone conversion.
    return {
        "source_scope": "returned hub-log entries, not entire requested interval",
        "matched_count": matched if type(matched) is int and matched >= 0 else None,
        "reported_count": count if type(count) is int and count >= 0 else None,
        "returned_entries": len(entries),
        "oldest_returned_time_as_reported": min(times) if times else None,
        "newest_returned_time_as_reported": max(times) if times else None,
        "time_zone_inferred_from_log_time": False,
        "complete_requested_window_proven": False,
        "log_entries_or_messages_reproduced": False,
    }


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


def final_claim_receipt_scope_index(
    receipts: list[dict], *, draft_answer: str | None = None,
    timezone_name: str | None = None,
) -> str:
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
            # A failed call cannot be treated as an empty event result.
            # Never reproduce arbitrary error text (it may contain private
            # arguments). A simple status code is safe diagnostic metadata.
            item["read_failed"] = True
            error = record.get("error")
            match = re.search(r"\bHTTP\s+([45]\d{2})\b", error,
                              re.IGNORECASE) if isinstance(error, str) else None
            if match is not None:
                item["read_error_class"] = "http"
                item["http_status"] = int(match.group(1))
            else:
                item["read_error_class"] = "unknown"
            item["no_matching_records_proven"] = False
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
                # Typed source-scope proof obligations are extracted from
                # already-returned values only. Never infer a physical event,
                # absence, retention guarantee or initiating actor from them.
                if record.get("name") == "hub_list_device_events":
                    guarantees = {
                        "uninterrupted_state_supported_by_this_source": (
                            event_scope.get("can_infer_uninterrupted_state_between_events")
                        ),
                        "requested_window_coverage_supported_by_this_source": (
                            event_scope.get("can_infer_requested_window_fully_covered")
                        ),
                        "older_events_excluded_by_this_source": (
                            event_scope.get("can_infer_older_events_absent")
                        ),
                        "original_store_independently_checked": (
                            event_scope.get("native_store_checked_independently")
                        ),
                    }
                    if any(type(value) is bool for value in guarantees.values()):
                        item["historical_continuity_proof_obligations"] = {
                            "scope": "this returned native event receipt only",
                            **{key: value for key, value in guarantees.items()
                               if type(value) is bool},
                            "zero_matching_rows_not_proof_of_no_transition": True,
                            "row_limit_not_reached_not_completeness_proof": True,
                        }
            event_names = _audit_event_groups(parsed.get("client_event_attribute_scope"))
            if event_names is not None:
                item["event_names_in_returned_rows"] = event_names
            selected_inputs = _audit_selected_inputs(
                parsed.get("client_config_source_map"))
            if selected_inputs is not None:
                item["config_selected_inputs"] = selected_inputs
            monitor = parsed.get("client_monitor_evidence_scope")
            if isinstance(monitor, dict):
                mon = _audit_scalars(monitor, _AUDIT_SOURCE_FIELDS)
                if isinstance(monitor.get("history"), dict):
                    mon["history"] = _audit_scalars(
                        monitor["history"], _AUDIT_MONITOR_HISTORY_FIELDS)
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
            log_scope = _audit_log_scope(original)
            if log_scope is not None:
                item["returned_log_scope"] = log_scope
        rows.append(item)
    temporal_anchors = temporal_receipt_fidelity_index(
        receipts, draft_answer
    ) if draft_answer else None
    completeness_anchors = original_event_completeness_index(
        receipts, draft_answer
    ) if draft_answer else None
    return json.dumps({
        "note": "Navigation index from returned receipt fields ONLY; not independent evidence. Do not infer unseen records absent. Failed calls are not empty successes. Inspect original receipts for full detail.",
        **({"temporal_event_anchors": temporal_anchors}
           if temporal_anchors is not None else {}),
        **({"original_event_completeness": completeness_anchors}
           if completeness_anchors is not None else {}),
        "receipt_grounding_anchors": receipt_grounding_anchors(receipts, timezone_name),
        "indexed_receipts": rows,
        "failed_calls_in_indexed_receipts": sum(
            row.get("read_failed") is True for row in rows),
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
            or bool(_CHECK_WITH_PROOF_AT_START.search(question))
            and bool(_EXPLICIT_PROOF_REQUEST.search(question))
        )
    )


def is_historical_continuity_question(question: str) -> bool:
    """Historical persisted-state evidence question, not a device/tool planner.

    Unlike a measurement report, these often start with Did/Was/Has and never
    contain show/report/history. Require all of read intent, persistence,
    a state dimension and a concrete past interval. No imperative writes.
    """
    return (
        isinstance(question, str)
        and not bool(_WRITE_INTENT_AT_START.search(question))
        and bool(_CONTINUITY_READ_START.search(question))
        and bool(_CONTINUITY_PERSISTENCE.search(question))
        and bool(_CONTINUITY_STATE_SUBJECT.search(question))
        and bool(_HISTORICAL_PERIOD.search(question)
                 or _CONTINUITY_FOR_PERIOD.search(question))
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
            or is_historical_continuity_question(question)
        )
    )


_APP_EXECUTION_SUBJECT = re.compile(
    r"\b(?:apps?|applications?|automations?|scheduler|rule\s+machine)\b",
    re.I,
)
_APP_EXECUTION_FACT = re.compile(
    r"\b(?:execut(?:e|ed|ion)|decisions?|trigger(?:ed|s)?|"
    r"ran|runs?|log(?:ged|s)?|history)\b",
    re.I,
)
_APP_EXECUTION_READ = re.compile(
    r"\b(?:find|show|inspect|identify|distinguish|summari[sz]e|report|"
    r"latest|newest|last|evidence|what|which|when)\b",
    re.I,
)


def is_app_execution_question(question: str) -> bool:
    """Eligibility only: app execution needs app-identity source verification.

    Does not guess installed app IDs, route a native tool, or infer execution.
    Generic category words are needed so an unrelated device-history request
    doesn't incur a new model round.
    """
    return (
        isinstance(question, str)
        and not bool(_WRITE_INTENT_AT_START.search(question))
        and any(
            _APP_EXECUTION_SUBJECT.search(clause)
            and _APP_EXECUTION_FACT.search(clause)
            and _APP_EXECUTION_READ.search(clause)
            for clause in re.split(r"[.!?\n]+", question)
        )
    )


APP_EXECUTION_REVIEW_PROMPT = """Read-only installed-application evidence checkpoint.
The question names or discusses an automation or application. An installed
Hubitat APP and a native DEVICE are distinct source categories. Before
claiming any app executed, establish the requested installed app's identity
using the actual offered app inventory/configuration or app-scoped logs,
not merely a same-named or nearby device listing. A command row from a
different recorded app identifies THAT recorded issuer, not the requested
app by alias. A device-report listener is not a command issuer.

The previous draft and a device label are not app identity evidence. If
the original receipts do not link the requested app and returned event,
consider a proportionate currently advertised READ-ONLY app/list/config/log
tool and exact arguments. YOU select any tool; no tool is required or
executed automatically. If exact app identity or execution remains
unverified, report the supported native command/state observations as
separate findings and mark the requested app unresolved. Configuration,
an app's self-reported history, recorded native command event, later
reported state and independent physical action are different fact types.

Do not change anything, read private credentials, infer a missing
historical action from zero returned rows, or treat an unsuccessful read as
proof of nonexistence. The final answer must be a user-facing result,
not commentary about this internal review.
"""


def review_kind(question: str) -> str | None:
    """Return one general reasoning goal, without prescribing MCP operations."""
    if is_causal_question(question):
        return "causal"
    if is_app_execution_question(question):
        return "app_execution"
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


def is_current_state_question(question: str) -> bool:
    """Current read intent only; never matches imperative writes by name.

    Eligibility is not proof the target exists, nor an instruction to use a
    particular tool. Ordinary ungrounded knowledge questions are excluded.
    """
    return (
        isinstance(question, str)
        and not bool(_WRITE_INTENT_AT_START.search(question))
        and bool(_CURRENT_READ_START.search(question))
        and bool(_CURRENT_READ_TIME.search(question))
        and bool(_CURRENT_READ_SUBJECT.search(question))
        and not bool(_CURRENT_READ_EXAMPLE.search(question))
    )


def review_prompt(kind: str) -> str:
    """Choose review guidance, not a tool or a computed answer."""
    if kind == "current_state":
        return CURRENT_STATE_REVIEW_PROMPT
    if kind == "historical_measurement":
        return MEASUREMENT_REVIEW_PROMPT
    if kind == "source_verification":
        return VERIFICATION_REVIEW_PROMPT
    if kind == "app_execution":
        return APP_EXECUTION_REVIEW_PROMPT
    if kind == "action_outcome":
        return ACTION_OUTCOME_REVIEW_PROMPT
    return SOURCE_REVIEW_PROMPT



def is_read_only_review_tool(name: str) -> bool:
    """Only exposed read-only core tools/gateways and local receipt reads.

    In the Hubitat MCP skill, hub_read_* gateways are read-only and flat
    hub_get_*, hub_list_* and hub_search_* tools are informational. Manage
    gateways can be mixed read/write and are deliberately not exposed during
    this supplemental checkpoint. The original model loop is untouched.
    """
    return name in {"homebrain_read_prior_evidence", "homebrain_read_device_monitor",
                    "homebrain_inspect_mcp_catalog", "homebrain_read_clock"} or (
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
    """Broad causal/reconstruction intent, independent of device or subsystem."""
    return (
        isinstance(question, str)
        and not bool(_WRITE_INTENT_AT_START.search(question))
        and bool(
            _CAUSAL_QUESTION.search(question)
            or _CAUSAL_RECONSTRUCTION.search(question)
        )
    )


CAUSAL_FOLLOW_THROUGH_PROMPT = """Unresolved causal-evidence follow-through (internal).
The original source-category check still leaves a material causal link
unverified, regardless of whether your previous answer sounds confident.
The preceding source review either made no new read or only collected
contextual/failed evidence without a potentially discriminating historical
source. The previous answer is NOT independent evidence. A successful hub metadata, current state,
mode or configuration read is not itself an event-time execution trace.
The user ALREADY authorised proportionate
READ-ONLY investigation; do not ask permission to perform a read.

Before accepting this unresolved conclusion, inspect the ORIGINAL receipts
and their returned time window. Separate four potential links:
1. The directly observed BEFORE state, not an assumed state.
2. The focal event and reporter, with its exact timestamp.
3. Any command and issuer, respecting command-versus-report chronological order.
4. Event-specific input/decision evidence and any later observations.

A command issuer is not the same as the internal reason for that command.
A notified listener or physical event tag is not an initiating actor.
Do not substitute a later sensor value or current configuration for a missing
historical observation, and do not infer absence from bounded event rows.

If a genuinely useful, currently advertised READ-ONLY source can distinguish
the remaining hypotheses or fill a missing temporal link, CHOOSE the exact
tool and arguments NOW. There is no mandated tool, device, log, app, source
order, or automatic request. Tool catalog entries are not execution receipts.
Do NOT merely restate that more logs might help if you can inspect such a
source safely now. If no proportionate read can improve the answer, finish
with supported facts and precisely delimited unknowns.

Never execute a write, device command, refresh that changes state, or unsafe
configuration probe; never infer consent to modify the home. This checkpoint
does not guarantee any source exists or that any causal hypothesis is true.
Do not mention this internal checkpoint.
"""



# Only classify well-known metadata/current-configuration reads as contextual.
# An unknown read-only tool could be genuinely discriminating and must NOT
# be declared useless by a name heuristic. No app/device/argument selection,
# causal inference, extra MCP read, or write occurs in this index.
_CONTEXT_ONLY_CAUSAL_READS = frozenset({
    "hub_get_info", "hub_list_modes", "hub_list_devices",
    "hub_get_device", "hub_list_apps", "hub_get_app_config",
})
_EVENT_TIME_CAUSAL_READS = frozenset({
    "hub_list_device_events", "hub_get_logs", "homebrain_read_device_monitor",
})
_CAUSAL_DELTA_MAX_RECEIPTS = 32


def causal_review_read_delta(receipts: list[dict], first_review_receipt_count: int) -> dict:
    """Describe whether the *extra* review reads could contain event-time facts.

    A nonempty original history or past application execution-log receipt is
    a potentially discriminating source TYPE; neither proves a relevant event,
    initiating app, input or physical outcome. Context-only metadata does not
    resolve an event-time causal gap. Unrecognized tools are conservatively
    counted as possibly material to avoid penalizing new MCP capabilities.
    """
    if (not isinstance(receipts, list) or type(first_review_receipt_count) is not int
            or first_review_receipt_count < 0
            or first_review_receipt_count > len(receipts)):
        return {"status": "unavailable", "only_contextual_or_unsuccessful_reads": False}
    from investigation_source_ledger import _response
    from native_device_event_receipt import original_device_event_history

    extra = receipts[first_review_receipt_count:]
    if len(extra) > _CAUSAL_DELTA_MAX_RECEIPTS:
        return {"status": "too_many_reads", "only_contextual_or_unsuccessful_reads": False}
    context_names: list[str] = []
    potential = 0
    unknown = 0
    failures = 0
    for receipt in extra:
        if not isinstance(receipt, dict):
            unknown += 1
            continue
        name = receipt.get("name")
        if not isinstance(name, str):
            unknown += 1
            continue
        if receipt.get("success") is not True:
            failures += 1
            continue
        if name in _CONTEXT_ONLY_CAUSAL_READS:
            if name not in context_names:
                context_names.append(name)
            continue
        if name == "hub_list_device_events":
            validated = original_device_event_history(receipt)
            if validated is not None and any(
                isinstance(item, dict) for item in validated[2][:250]
            ):
                potential += 1
            else:
                # A zero-row or unverifiable history is not event-time proof.
                if name not in context_names:
                    context_names.append(name)
            continue
        if name == "hub_get_logs":
            args = receipt.get("arguments")
            args = args if isinstance(args, dict) else {}
            _, data = _response(receipt)
            if (args.get("mode") == "past" and args.get("appId") is not None
                    and isinstance(data, dict) and data.get("mode") == "past"
                    and isinstance(data.get("entries"), list)
                    and any(isinstance(item, dict) and item.get("type") == "app"
                            for item in data["entries"][:250])):
                potential += 1
            elif name not in context_names:
                context_names.append(name)
            continue
        if name == "homebrain_read_device_monitor":
            args = receipt.get("arguments")
            if isinstance(args, dict) and args.get("mode") in ("history", "compare"):
                potential += 1
            elif name not in context_names:
                context_names.append(name)
            continue
        # Future/third-party READ-ONLY contracts must not be blanket-scored
        # as useless without a validated source interpretation.
        unknown += 1

    return {
        "status": "assessed",
        "review_receipts": len(extra),
        "contextual_read_names": context_names[:8],
        "failed_attempt_count": failures,
        "potential_event_time_read_count": potential,
        "unclassified_read_count": unknown,
        "only_contextual_or_unsuccessful_reads": potential == 0 and unknown == 0,
        "contextual_does_not_prove_no_event_time_source_exists": True,
        "potential_source_type_is_not_causal_proof": True,
    }


def should_recheck_causal_evidence(
    question: str, *, review_kind_name: str | None,
    first_review_receipt_count: int, receipt_count: int,
    already_rechecked: bool, candidate_answer: str,
    remaining_seconds: float, has_action_receipt: bool,
    available_read_tools: bool,
    review_read_delta: dict | None = None,
    structural_source_gap: bool = False,
) -> bool:
    """One model-selected read opportunity when original causal sources are weak.

    The evidence gap is derived from native receipt categories, not confidence
    or phrase patterns in the draft. This does not force any source read.
    A strict time
    budget avoids turning every straightforward Ask into extra paid rounds.
    """
    return (
        not already_rechecked
        and review_kind_name == "causal"
        and is_causal_question(question)
        and not _EXPLICIT_NO_FRESH_READ.search(question)
        and available_read_tools
        and not has_action_receipt
        and first_review_receipt_count > 0
        and (receipt_count == first_review_receipt_count
             or (isinstance(review_read_delta, dict)
                 and review_read_delta.get("status") == "assessed"
                 and review_read_delta.get(
                     "only_contextual_or_unsuccessful_reads") is True))
        and remaining_seconds > 25
        and isinstance(candidate_answer, str)
        and (structural_source_gap
             or bool(_CAUSAL_UNRESOLVED.search(candidate_answer)))
    )


# A user may prohibit accessing the hub, but "do not change anything" is a
# read-only safety boundary, NOT a prohibition on harmless observation.
_EXPLICIT_NO_FRESH_READ = re.compile(
    r"\b(?:do\s+not|don't|without)\s+"
    r"(?:(?:any|new|further|fresh)\s+)?"
    r"(?:(?:mcp|hub|tool)\s+)?"
    r"(?:read|reads|query|queries|call|calls|access|contact)\b"
    r"|\b(?:do\s+not|don't)\s+use\s+(?:any\s+|new\s+)?tools\b"
    r"|\b(?:do\s+not|don't|without)\s+make\s+"
    r"(?:(?:any|new|further|fresh)\s+){0,2}"
    r"(?:(?:mcp|hub|tool)\s+)?(?:calls|reads|queries)\b"
    r"|\b(?:no\s+(?:new|further|fresh)\s+(?:tool\s+)?(?:calls|reads|queries))\b"
    r"|\b(?:use\s+only|only\s+use|rely\s+only\s+on)\s+"
    r"(?:the\s+)?(?:prior|previous|earlier|existing)\s+"
    r"(?:receipts|evidence|results)\b",
    re.IGNORECASE,
)


FRESH_SOURCE_RECOVERY_PROMPT = """Missing fresh source — READ-ONLY recovery (internal).
The previous answer is not source evidence. No successful current-request
native or separate-monitor observation was established. Some read attempts
may have FAILED, timed out or been rejected; those attempts are NOT an empty
history, zero measured values or proof that the target is absent. Inspect
the actual original receipt errors before considering a different available
read-only source. Earlier conversation receipts may describe a DIFFERENT
target or window; they are neither exhaustive nor a prohibition on a new read.

The user's "do not change anything" instruction forbids device/rule/settings
WRITES; it DOES NOT forbid proportionate READ-ONLY device identification,
event-history or other observational queries. The current question already
authorizes those observations; do not request additional permission.

Before repeating an unsupported "no receipts" conclusion, independently choose
appropriate advertised READ-ONLY tool(s) and arguments NOW if useful for this
request. Do not assume a target ID, invent a source, mandate one tool, or reuse
another device's receipts. An attribute-filtered history cannot enumerate
all commands, and a state reporter/listener is not a proven initiator.
If no suitable authorized read exists or a genuine access restriction applies,
state precisely which current-request evidence was NOT obtained. Never issue
a write, change a setting, or treat prior receipts as current-request reads.
Do not mention this internal checkpoint.
"""


def should_offer_fresh_source_recovery(
    question: str, *, kind: str | None, has_current_read_attempt: bool,
    available_read_tools: bool, has_action_receipt: bool,
    has_successful_current_read: bool | None = None,
) -> bool:
    """Re-use the EXISTING read-only review when no source read succeeded.

    The original has_current_read_attempt input remains for compatibility
    with the old boolean contract. When supplied, source-derived
    has_successful_current_read takes precedence: a failed/timed-out
    read is not evidence that an observation was retrieved. This selects
    no tool, adds no model round, and retains explicit no-read restrictions.
    """
    return (
        kind in ("historical_measurement", "causal", "source_verification")
        and isinstance(question, str)
        and not _WRITE_INTENT_AT_START.search(question)
        and not _EXPLICIT_NO_FRESH_READ.search(question)
        and not (has_current_read_attempt if has_successful_current_read is None
                 else has_successful_current_read)
        and available_read_tools
        and not has_action_receipt
    )



def should_prompt_outcome_history_gap(
    question: str, *, review_kind_name: str | None,
    source_frontier: dict, candidate_answer: str,
    has_action_receipt: bool = False,
) -> bool:
    """Guide existing review about outcome evidence, not tool selection."""
    from causal_outcome_frontier import should_prompt_outcome_first_review
    return (
        is_causal_question(question)
        and not _EXPLICIT_NO_FRESH_READ.search(question)
        and should_prompt_outcome_first_review(
            question, review_kind_name=review_kind_name,
            source_frontier=source_frontier, candidate_answer=candidate_answer,
            has_action_receipt=has_action_receipt,
        )
    )


def should_prompt_controller_decision_gap(
    question: str, *, review_kind_name: str | None,
    source_frontier: dict, has_action_receipt: bool = False,
) -> bool:
    """Prompt the EXISTING review, never dispatch an app/tool/extra round."""
    return (
        review_kind_name == "causal"
        and is_causal_question(question)
        and not _EXPLICIT_NO_FRESH_READ.search(question)
        and not has_action_receipt
        and isinstance(source_frontier, dict)
        and source_frontier.get(
            "controller_decision_source_unchecked_for_model_review"
        ) is True
    )


def should_prompt_historical_status_gap(
    question: str, *, review_kind_name: str | None,
    source_frontier: dict, has_action_receipt: bool = False,
) -> bool:
    """Offer source-TYPE clarification inside the EXISTING model review.

    This must NEVER dispatch a tool, add a model round, override explicit
    no-new-read instructions, or apply to native write/action requests.
    """
    return (
        review_kind_name == "historical_measurement"
        and isinstance(question, str)
        and not _WRITE_INTENT_AT_START.search(question)
        and not _EXPLICIT_NO_FRESH_READ.search(question)
        and not has_action_receipt
        and isinstance(source_frontier, dict)
        and source_frontier.get("status_only_historical_gap_for_model_review") is True
    )


def should_review_completion(
    question: str, *, available_tools: bool, already_reviewed: bool,
    remaining_seconds: float, has_action_receipt: bool = False,
    has_tool_receipts: bool = False, candidate_answer: str = "",
) -> bool:
    """Only open a model review when there is a chance to investigate safely.

    A short deadline leaves the original model response intact rather than
    risking a second model timeout. No MCP call is made by this helper.
    """
    kind = review_kind(question)
    return (
        not already_reviewed
        and available_tools
        and remaining_seconds > 8
        and (
            (kind is not None and (kind != "app_execution" or has_tool_receipts))
            or has_action_receipt
            or (not has_tool_receipts and is_current_state_question(question)
                and is_deferred_read_draft(candidate_answer))
        )
    )
