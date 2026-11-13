"""One bounded source-coverage recovery for unfinished explicit device actions.

The client can broaden a previously filtered *read-only inventory* once.
This does not infer device matches, select a controller, authorize a write,
map command names, or rewrite the model's answer. The model remains
responsible for source-grounded identity and native command selection.
"""
from __future__ import annotations

import re


_DEVICE_IMPERATIVE = re.compile(
    r"^\s*(?:please\s+)?(?:turn|switch|set|adjust|change|enable|disable|"
    r"start|stop|pause|play|mute|unmute|block|unblock|allow|deny|"
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
    has_native_write_attempt: bool,
) -> bool:
    """Give the model broad source evidence only after a narrow action dead end.

    No action, command or target is selected by this predicate. The model has
    to identify a matching control surface and check its native commands.
    """
    return (
        not already_recovered
        and not source_review_invoked
        and not has_native_write_attempt
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
) -> bool:
    """Offer ONE model-led completion opportunity after source recovery.

    The candidate device is NOT selected by this code. It simply verifies
    that the model actually obtained a successful detailed source receipt
    after the broad inventory read, but has not submitted any native write.
    No automatic native writer or extra control permission is introduced.
    """
    if (
        not inventory_recovery_invoked
        or already_prompted
        or source_review_invoked
        or has_native_write_attempt
        or remaining_seconds <= 8
        or not is_explicit_device_imperative(question)
    ):
        return False
    last_recovery = max(
        (i for i, row in enumerate(receipts)
         if row.get("client_inventory_coverage_recovery")),
        default=-1,
    )
    if last_recovery < 0:
        return False
    return any(
        row.get("name") == "hub_get_device"
        and row.get("success") is True
        for row in receipts[last_recovery + 1:]
    )


DEVICE_ACTION_FOLLOW_THROUGH_PROMPT = """Original user already gave a direct
device-control instruction. This is ONE final opportunity to resolve the
requested action after the original broad inventory and device-detail reads.
Your previous draft did not execute anything. Recheck the intended TARGET,
PHYSICAL EFFECT and TIMING against the ORIGINAL successful native receipts.

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
