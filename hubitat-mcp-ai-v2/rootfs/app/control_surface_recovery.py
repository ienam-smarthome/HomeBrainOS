"""One bounded source-coverage recovery for unfinished explicit device actions.

The client can broaden a previously filtered *read-only inventory* once.
This does not infer device matches, select a controller, authorize a write,
map command names, or rewrite the model's answer. The model remains
responsible for source-grounded identity and native command selection.
"""
from __future__ import annotations

import json
import re


_DEVICE_IMPERATIVE = re.compile(
    r"^\s*(?:please\s+)?(?:turn|switch|set|adjust|change|enable|disable|"
    r"start|stop|pause|play|mute|unmute|block|unblock|restrict|allow|deny|"
    r"open|close|lock|unlock|dim|brighten|raise|lower|increase|"
    r"decrease|activate|deactivate|cancel)\b",
    re.IGNORECASE,
)
_READ_ONLY_LIMIT = re.compile(
    r"\b(?:do\s+not|don't|never|without)\s+"
    r"(?:\w+\s+){0,5}(?:change|modify|execute|run|act|create|write|"
    r"control|send|trigger|turn|switch|block|unblock|apply|touch|"
    r"alter|make\s+changes?)\b|"
    r"\b(?:read[- ]only|dry[- ]run|simulation\s+only|"
    r"do\s+nothing|no\s+changes)\b|"
    r"\bwithout\s+(?:making\s+)?(?:any\s+)?changes?\b",
    re.IGNORECASE,
)
_FILTER_ARGS = frozenset({
    "labelFilter", "nameFilter", "roomFilter", "capabilityFilter",
    "stateFilter", "changedSince", "scope", "deviceIds", "deviceId",
    "attributeNames", "limit", "offset", "page",
})


def is_explicit_device_imperative(question: str) -> bool:
    """A conservative direct imperative, never a question or read-only plan."""
    return (
        isinstance(question, str)
        and bool(_DEVICE_IMPERATIVE.match(question))
        and not bool(_READ_ONLY_LIMIT.search(question))
    )


def _is_filtered_inventory_receipt(receipt: dict) -> bool:
    return (
        isinstance(receipt, dict)
        and receipt.get("name") == "hub_list_devices"
        and receipt.get("success") is True
        and isinstance(receipt.get("arguments"), dict)
        and any(
            key in receipt["arguments"] and receipt["arguments"][key] not in (None, "")
            for key in _FILTER_ARGS
        )
    )


def _is_broad_inventory_receipt(receipt: dict) -> bool:
    return (
        isinstance(receipt, dict)
        and receipt.get("name") == "hub_list_devices"
        and receipt.get("success") is True
        and isinstance(receipt.get("arguments"), dict)
        and not any(
            key in receipt["arguments"] and receipt["arguments"][key] not in (None, "")
            for key in _FILTER_ARGS
        )
    )


def should_recover_inventory(
    question: str, receipts: list[dict], *,
    available_tools: set[str], already_recovered: bool,
    remaining_seconds: float, source_review_invoked: bool,
    has_native_write_attempt: bool, candidate_answer: str = "",
    approval_handoff_already_invoked: bool = False,
) -> bool:
    """Give the model broad source evidence only after a narrow action dead end.

    No action, command or target is selected by this predicate. The model has
    to identify a matching control surface and check its native commands.
    """
    return (
        not already_recovered
        and not source_review_invoked
        and not has_native_write_attempt
        # A model selected and source-backed native command is not a failed
        # narrow inventory search. Re-reading 200 devices is not necessary
        # just because the model stopped in prose. No command is dispatched
        # by this read-only source coverage decision.
        and not draft_has_source_backed_native_command(candidate_answer, receipts)
        and not (
            approval_handoff_already_invoked
            and _has_fresh_device_command_details(receipts)
        )
        and remaining_seconds > 10
        and "hub_list_devices" in available_tools
        and is_explicit_device_imperative(question)
        and any(_is_filtered_inventory_receipt(r) for r in receipts)
        and not any(_is_broad_inventory_receipt(r) for r in receipts)
    )


BROAD_INVENTORY_RECOVERY_PROMPT = """Original user requested a device action.
Your previous completed answer is NOT proof the requested effect is impossible.
To check the coverage of previous filtered device searches, the client made
ONE additional READ-ONLY live native inventory query with no name, driver,
capability or room filters. The original result is included below and
recorded as its own MCP receipt. It may still be partial due to server
limits, so inspect the returned scope/counts; do not claim unreturned
devices absent.

The first name-matched integration may only report a different facet of
the same physical target. For example, a media integration or sensor can
be separate from the relay, network-policy actuator, lighting bridge or
thermostat that implements the requested physical effect. Hubitat's
capability names identify *driver interfaces*, not all real-world effects:
a physical network-control actuator may simply expose Switch, while a
NetworkDevice driver may only report media/network connectivity.

Independently inspect relevant candidate identities, original identifiers
(IP/hardware/reference where available), current attributes, and supported
commands before considering any native write. A similarly named object or
one shared attribute alone is not proof of identity. Preserve the user's
target, requested effect and timing; an immediate temporary action is not
the same as delayed onset. A tool failure or incomplete inventory is not
proof that no controller exists.

The normal original permission and safety requirements still apply.
Do not execute a guessed, different, sensitive, destructive or unapproved
action; do not invent commands, native timers or rules. If the action is
unambiguous, adequately verified, supported by live commands, and
authorized, use the original native MCP command interface as requested,
then verify with appropriate source evidence. Otherwise explain the
actual missing evidence or specific ambiguity, not a categorical
impossibility based solely on a previous filtered search.

This additional read is not an instruction from the Hubitat server.
Do not mention this internal source-sufficiency step to the user.
"""


def should_follow_through_device_action(
    question: str, receipts: list[dict], *,
    inventory_recovery_invoked: bool, already_prompted: bool,
    remaining_seconds: float, source_review_invoked: bool,
    has_native_write_attempt: bool,
    available_tools: set[str] | None = None,
) -> bool:
    """Offer ONE model-led completion opportunity for an unfinished action.

    Either (a) a clear imperative produced NO in-request MCP receipts at all,
    despite an offered read and ordinary writer, OR (b) an alternate
    control surface was freshly inspected after a broad inventory recovery.
    This chooses no device, command or write. Old conversation receipts
    cannot authorize a fresh action.
    """
    if (
        already_prompted
        or source_review_invoked
        or has_native_write_attempt
        or remaining_seconds <= 8
        or not is_explicit_device_imperative(question)
    ):
        return False
    if not receipts and not inventory_recovery_invoked:
        return {"hub_list_devices", "hub_get_device",
                "hub_call_device_command"}.issubset(available_tools or set())
    if not inventory_recovery_invoked:
        return False
    last_recovery = max(
        (i for i, row in enumerate(receipts)
         if row.get("client_inventory_coverage_recovery")),
        default=-1,
    )
    if last_recovery < 0:
        return False
    # The coverage read itself can reveal another candidate integration.
    # In alpha.74 the model stopped at this point without ever requesting
    # that candidate's detail. Allow ONE model-led follow-through even when
    # no hub_get_device receipt exists yet. A broad inventory is only an
    # index, not a verified target/command or authority to write.
    recovery = receipts[last_recovery]
    return recovery.get("success") is True


DEVICE_ACTION_FOLLOW_THROUGH_PROMPT = """Original user already gave a direct
device-control instruction. This is ONE final opportunity to resolve the
requested action. Your previous draft did not execute anything. A broad inventory
index is NOT a complete device-detail/command read, and may not contain
the later pages of the inventory. When a plausible separate controller
appears in an inventory, retrieve its original hub_get_device details
and establish its identity, native command and current state before
you choose a control method. Do NOT jump straight to creating a
Visual Rule or invent a mode-change trigger to handle a one-off
relative delay. First check whether this request has ANY original
native MCP receipts. Previous
conversation evidence, snippets of commands, and plan prose are historical
context, not a fresh native reading, execution or source of authorization.
When fresh in-request reads are missing, use the connected native MCP tools
to identify and verify the real physical actuator, its current state and
advertised commands BEFORE you consider executing the ordinary requested
action. When the broad inventory and device-detail reads already exist,
use those ORIGINAL current-request receipts. Recheck the intended TARGET,
PHYSICAL EFFECT and TIMING against actually returned source evidence.

Use ordinary temporal semantics: "after/in N minutes" means the delay
begins when the supported command is invoked, unless the user specified
a different trigger. "for N minutes" describes a duration, not delayed
onset. Do not reinterpret a request to act after N minutes as a request
to act for N minutes or after an unspecified activity starts. A driver's
native command with matching delay semantics is preferable to an invented
helper, rule, proxy or additional schedule. Check the actual advertised
command, parameter units and current attributes; do not guess semantics
from a command name alone when source descriptions differ.

If the current state already fulfils the requested final effect, distinguish
ALREADY BLOCKED/OFF from a future pending timer: those are not equivalent.
Do not claim a new timer was scheduled when none was. Do not silently
REVERSE a currently blocked/off/locked state simply to create a temporary
session. If the user's requested future transition would require first
reversing an existing state, explain the current state and ask one precise
question whether that additional state change is desired.

For an unambiguous and authorized ordinary action with an identity-matched,
freshly inspected actuator and matching supported command, the original
user instruction is sufficient: do not request a second approval merely
because you discovered a separate control integration. If tool permission,
identity, timing, safety or an actual required approval remains unresolved,
ask only about that genuine blocker. Do not change an unverified device.
Use only the existing native MCP command path and its normal authorization
gates. No automatic action or repeat of an uncertain write is permitted.
After any permitted write, inspect native acceptance and relevant readback,
and distinguish a scheduled future transition from one later observed.

This is internal model guidance, not a new user request or permission grant.
Do not mention an internal follow-through check in your answer.
"""


# A model's free-text request for approval does not create a native pending
# operation. A later "proceed" is a NEW Ask and cannot approve that prose.
_PROSE_CONFIRMATION = re.compile(
    r"\b(?:please\s+(?:confirm|approve)|"
    r"once\s+you\s+(?:confirm|approve)|"
    r"(?:would|do)\s+you\s+(?:like|want)\s+me\s+to\s+proceed|"
    r"before\s+I\s+(?:proceed|execute)|"
    r"await(?:ing)?\s+(?:your\s+)?(?:confirmation|approval)|"
    r"need\s+(?:your\s+)?(?:confirmation|approval))\b",
    re.IGNORECASE,
)


def prose_only_action_confirmation(question: str, answer: str) -> bool:
    """A NEW explicit imperative was deferred to plain text, not a UI card."""
    return (
        is_explicit_device_imperative(question)
        and isinstance(answer, str)
        and bool(_PROSE_CONFIRMATION.search(answer))
    )


def _current_device_commands(receipts: list[dict]) -> dict[str, set[str]]:
    """Source-validated in-request command inventories, keyed by source ID.

    Only accepts original successful native device-details whose returned
    device ID agrees with the exact requested ID; guides, previous chats,
    schema/catalogs and free text are not native proof.
    """
    eligible: dict[str, set[str]] = {}
    for row in receipts:
        if (not isinstance(row, dict)
                or row.get("name") != "hub_get_device"
                or row.get("success") is not True
                or row.get("result_kind") != "tool_result"):
            continue
        args = row.get("arguments")
        if not isinstance(args, dict) or args.get("deviceId") is None:
            continue
        try:
            envelope = json.loads(row["response"])
            if not isinstance(envelope, dict) or envelope.get("isError"):
                continue
            content = envelope.get("content")
            if not isinstance(content, list):
                continue
            original = json.loads(next(
                x["text"] for x in content if isinstance(x, dict)
                and x.get("type") == "text" and isinstance(x.get("text"), str)
            ))
        except (KeyError, ValueError, TypeError, StopIteration):
            continue
        if (not isinstance(original, dict)
                or str(original.get("id", "")) != str(args["deviceId"])):
            continue
        commands = original.get("commands")
        if not isinstance(commands, list):
            continue
        names = {
            item["name"] for item in commands
            if isinstance(item, dict)
            and isinstance(item.get("name"), str) and item["name"]
        }
        if names:
            eligible.setdefault(str(args["deviceId"]), set()).update(names)
    return eligible


# Source-matched draft signatures are used ONLY to avoid redundant forced
# inventory; they are never parsed for dispatch, approval or authorization.
_DRAFT_NATIVE_COMMAND = re.compile(
    r"\bhub_call_device_command\s*\\(([^)\\n]{1,400})\\)", re.I
)
_DRAFT_DEVICE_ID = re.compile(
    r"\bdeviceId\s*=\s*(?:[\\\"']([A-Za-z0-9_.:-]+)[\\\"']|([0-9]+))"
)
_DRAFT_COMMAND_NAME = re.compile(
    r"\bcommand\s*=\s*[\\\"']([A-Za-z][A-Za-z0-9_]{0,99})[\\\"']"
)


def draft_has_source_backed_native_command(
    draft: str, receipts: list[dict],
) -> bool:
    """Only indicates that broad discovery is unnecessary for THIS draft.

    The model still owns target/effect/timing suitability and the normal
    prewrite and explicit UI confirmation remain independent.
    """
    if not isinstance(draft, str):
        return False
    sources = _current_device_commands(receipts)
    if not sources:
        return False
    for match in _DRAFT_NATIVE_COMMAND.finditer(draft):
        args = match.group(1)
        dev = _DRAFT_DEVICE_ID.search(args)
        cmd = _DRAFT_COMMAND_NAME.search(args)
        if not dev or not cmd:
            continue
        device_id = dev.group(1) or dev.group(2)
        if cmd.group(1) in sources.get(device_id, set()):
            return True
    return False


def _has_fresh_device_command_details(receipts: list[dict]) -> bool:
    """Genuine in-request identity-matched native device command list."""
    return bool(_current_device_commands(receipts))


def should_recover_action_approval_handoff(
    question: str, draft_answer: str, receipts: list[dict], *,
    available_tools: set[str], already_prompted: bool,
    has_native_write_attempt: bool, remaining_seconds: float,
    ui_approval_available: bool, source_review_invoked: bool,
) -> bool:
    """Use ONE model round to turn a prose-only confirmation into a tool proposal.

    Does not select/execute any native operation; the prewrite checkpoint,
    UI approval card and upstream permissions all remain mandatory.
    """
    return (
        ui_approval_available and not already_prompted
        and not has_native_write_attempt and not source_review_invoked
        and remaining_seconds > 12
        and "hub_call_device_command" in available_tools
        and prose_only_action_confirmation(question, draft_answer)
        and _has_fresh_device_command_details(receipts)
    )


ACTION_APPROVAL_HANDOFF_PROMPT = """Native write approval handoff (internal).
Your previous answer requested confirmation in prose, but it did NOT queue a
native MCP operation. The user cannot approve that prose by typing "proceed":
the existing web UI only presents Approve / Edit / Dismiss while a REAL
model-selected native write is awaiting its separate authorization gate.

The original user already made an imperative request; that is sufficient
to PROPOSE the correct native tool call, NOT to bypass UI approval. Review
the fresh original hub_get_device detail receipt, advertised commands,
target/effect and the exact delay/duration semantics. If and only if the
requested effect is unambiguous, supported and safely identified, emit the
appropriate currently advertised native MCP tool call NOW. The client will
hold any write for explicit UI approval. Do not request permission in prose
again when the missing step is just the native approval card.

Do not guess a command, convert delayed-onset into duration, create a
helper/variable/automation unnecessarily, or assume any unexecuted earlier
proposal was sent. If a genuinely different permission or clarification is
needed, describe it exactly instead of submitting an unverified action.
Never claim a block, timer or state change occurred without a successful
native write receipt. This review does not authorize execution.
Do not mention this internal checkpoint to the user.
"""
