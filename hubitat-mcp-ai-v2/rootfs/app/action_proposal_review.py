"""A bounded, model-led pre-dispatch reconsideration of a proposed action.

Only selected native tool names and structured arguments determine whether
an unexecuted operation is mutating. The client does not select a target,
route a command, create a rule, infer the real-world effect or authorize a
write. Its checkpoint invites the model to use live MCP sources.
"""
from __future__ import annotations

import json
import re
from typing import Any

from action_intent_guard import native_automation_writer
from one_off_rule_policy import is_native_rule_read
from investigation_review import is_read_only_review_tool


PREWRITE_PROPOSAL_PROMPT = """Pre-dispatch action evidence review. The actions
in the proposal below were NOT sent, executed, authorised or confirmed. The
assistant's earlier plan, a device label and older conversation receipts are
not proof of the user's requested real-world effect.

Reassess the original user's TARGET, PHYSICAL EFFECT and TIMING as THREE
separate requirements. Is there *current-request* native source evidence
identifying an actuator capable of that effect, its supported commands and
the requested schedule semantics? A similarly named media/monitor/helper
device might control something else. An 'off' switch command may not mean
network blocking, heating off, or any other downstream physical effect.
A filtered device search may omit a differently named control actuator.
**Source-sufficiency and time budget:** if current-request ORIGINAL
hub_get_device details already establish the actual actuator, its advertised
native command and matching timing semantics, choose the appropriate native
tool proposal directly and let the existing user approval gate operate.
Do not re-list the whole inventory, query unrelated rule/configuration
surfaces or create persistent helpers merely to reconsider an already
supported direct one-off operation. This is not authorization to assume the
first similar-looking device is the real controller. If identity, physical
effect, delay/duration, state reversal or permission is genuinely unclear,
read proportionate discriminating sources and explain the blocker. An
ambiguous media integration is not a verified internet-policy actuator.
When a directly supported command exists, do not substitute an event-rule
based on elapsed usage for a delay measured from the user's request.
A proposed command remains unexecuted until the UI explicitly approves it.

For a ONE-OFF action after a relative delay, independently compare the
advertised device-owned timer/deferred command, a genuine one-time scheduled
rule (if its one-shot trigger and lifecycle are supported by the native
rule engine), and other verified native options. A persistent event-triggered
Visual Rule with 'wait' does NOT by itself become one-off just because you
activate its helper switch once: it remains capable of firing again. Do not
invent a future trigger, needlessly construct a virtual helper, or treat a
media power/off command as some other requested effect without evidence.
Do not automatically prefer a particular tool; if a real one-off native rule
is justified, inspect its source-reported trigger, action type, and lifecycle.

For any numeric duration/offset derived from a wall-clock time, use a
read-only CLIENT clock/target arithmetic receipt (and hub timezone source
if available), explicitly identify the requested target instant, and
check the derived number of minutes before dispatch. A guessed clock or
a rounded proposal number is not a calculation. If no current clock receipt
exists, read it before submitting a time-derived command. This checkpoint
does not select or calculate the user's target for you.

If the previous proposal is unsupported, abandon it and independently
choose relevant READ-ONLY MCP tools before acting. If the sources and
permissions truly support it, submit the intended native operation through
the normal MCP catalog and user approval gates. You may also report a real
blocker. This is a review of your OWN unsent proposal, NOT a new user request,
approval or instruction to manufacture an action. Never claim the proposal
executed. Do not mention this internal checkpoint in the final answer.
"""


def is_native_action_proposal(name: str, args: dict[str, Any], catalog: list[dict]) -> bool:
    """Classify a proposed mutating entry point without parsing the user prompt."""
    if is_read_only_review_tool(name) or is_native_rule_read(name, args):
        return False
    # A selected, known writer outranks a gateway-level readOnlyHint.
    # Gateway declarations may cover mixed leaf catalogues.
    if native_automation_writer(name, args):
        return True
    leaf = args.get("tool") if isinstance(args, dict) else None
    if isinstance(leaf, str) and is_read_only_review_tool(leaf):
        return False
    declared = next((item for item in catalog
                     if isinstance(item, dict) and item.get("name") == name), {})
    annotation = declared.get("annotations") if isinstance(declared, dict) else None
    if isinstance(annotation, dict) and annotation.get("readOnlyHint") is True:
        return False
    if native_automation_writer(name, args):
        return True
    if name in {"hub_call_device_command", "hub_manage_virtual_device"}:
        return True
    return name.startswith(("hub_set_", "hub_create_", "hub_update_",
                            "hub_delete_", "hub_manage_", "hub_call_",
                            "hub_reboot", "hub_shutdown"))


def is_persistent_construct(name: str, args: dict[str, Any]) -> bool:
    """Known persistent automation/helper creation, never a native device timer."""
    if native_automation_writer(name, args):
        return True
    return name == "hub_manage_virtual_device" and args.get("action") == "create"


def has_current_native_evidence(receipts: list[dict]) -> bool:
    """Require at least one successful in-request domain read before creation.

    A tool guide, schema/catalog probe, prior-conversation receipt, or
    failure is not evidence of the current target. Further suitability
    remains the MODEL'S responsibility; this check never maps devices.
    """
    for receipt in receipts:
        name = receipt.get("name")
        args = receipt.get("arguments")
        leaf = args.get("tool") if isinstance(args, dict) else None
        actual_read = (
            isinstance(name, str)
            and (name.startswith(("hub_get_", "hub_list_", "hub_read_"))
                 or (name.startswith("hub_manage_")
                     and isinstance(leaf, str)
                     and is_read_only_review_tool(leaf)))
            and name not in {"hub_get_tool_guide", "hub_get_skill"}
        )
        if (receipt.get("success") is True and actual_read
                and receipt.get("operation_executed") is not False
                and receipt.get("result_kind") not in (
                    "tool_catalog", "local_catalog_read", "prior_evidence_read",
                )):
            return True
    return False


def _proposed_device_ids(calls) -> set[str]:
    """Device ids named in the structured arguments of proposed native calls."""
    found: set[str] = set()

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ("deviceId", "device_id") and isinstance(item, (str, int)):
                    found.add(str(item))
                else:
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    for call in calls or []:
        if isinstance(call, dict):
            function = call.get("function") or {}
            args = function.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = None
            walk(args)
    return found


def reinstate_reviewed_proposal(original_calls, receipts):
    """Return the original proposal when every targeted device id appears in a successful read.

    Used when the pre-write review round ends without a call: the draft was never sent, and
    reinstating it only reaches the user's approval card (nothing is written without it).
    Structural: reads call arguments and receipt text for ids, never the user's wording.
    """
    ids = _proposed_device_ids(original_calls)
    if not ids:
        return None
    seen = " ".join(str(r.get("response") or "") for r in receipts
                    if isinstance(r, dict) and r.get("success") is True and r.get("read_only"))
    if all(re.search(r'(?<![0-9])' + re.escape(i) + r'(?![0-9])', seen) for i in ids):
        return list(original_calls)
    return None


def _canonical_write(args) -> str:
    """Arguments without waitFor, with key order fixed, for comparing repeated writes."""
    if not isinstance(args, dict):
        return json.dumps(args, sort_keys=True, default=str)
    kept = {k: v for k, v in args.items() if k != "waitFor"}
    return json.dumps(kept, sort_keys=True, default=str)


def repeat_write_refusal(name: str, args, receipts, catalog) -> str | None:
    """Refuse re-sending a native write that this request already got accepted.

    Compares tool name and structured arguments (waitFor ignored) with earlier successful
    write receipts. Never reads the user's wording.
    """
    if not is_native_action_proposal(name, args, catalog):
        return None
    wanted = _canonical_write(args)
    for row in receipts:
        if (isinstance(row, dict) and row.get("name") == name and row.get("success") is True
                and row.get("possible_native_action")
                and _canonical_write(row.get("arguments")) == wanted):
            return ("This exact write was already accepted earlier in this request; it was not "
                    "sent again. Confirm the result with a read (for example hub_list_devices "
                    "with deviceIds and waitFor) and answer from that read.")
    return None
