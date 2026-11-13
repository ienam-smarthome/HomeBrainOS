"""A bounded, model-led pre-dispatch reconsideration of a proposed action.

Only selected native tool names and structured arguments determine whether
an unexecuted operation is mutating. The client does not select a target,
route a command, create a rule, infer the real-world effect or authorize a
write. Its checkpoint invites the model to use live MCP sources.
"""
from __future__ import annotations

from typing import Any

from action_intent_guard import native_automation_writer
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
Consider a proportionate broader native inventory or focused command/schema
read if the source evidence does not distinguish the available choices.

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
    if is_read_only_review_tool(name):
        return False
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
        if (receipt.get("success") is True
                and isinstance(name, str)
                and name.startswith(("hub_get_", "hub_list_", "hub_read_"))
                and name not in {"hub_get_tool_guide", "hub_get_skill"}):
            return True
    return False
