"""Pure confirmation decisions for structured Hubitat tool calls.

The policy decides whether an already-classified call needs confirmation,
validates a proposed confirmation group, and builds deterministic user-facing
wording. It never stores pending actions, consumes confirmation replies, or
executes tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from enum import Enum
from typing import Any

from tool_registry import HUB_UPDATE_FIRMWARE_TOOL, ToolEffect


# Nested gateway operation names (the "tool" value inside a hub_manage_*
# call's own {"tool": ..., "args": {...}} envelope) confirmed, by directly
# inspecting each gateway's live MCP schema, to declare their OWN
# confirm/confirm=true parameter. This is deliberately an explicit allowlist
# rather than "any nested args object" -- some operations that share a
# gateway with confirm-bearing ones do NOT have a confirm field at all and
# instead verify success their own way (hub_call_device_command uses
# waitFor-based state verification; hub_set_rule_paused/hub_call_rule/
# hub_set_rule_private_boolean are routine RM runtime control, not
# destructive; hub_update_custom_rule's schema has no confirm field at all).
# Sending an unrequested "confirm" key to one of those could be silently
# ignored or could trip an unexpected-parameter rejection upstream -- since
# that can't be verified without live-testing every single operation, the
# safe default is to only inject where the schema is already known to
# expect it, and extend this set as new confirm-bearing operations are
# discovered rather than guessing broadly.
_NESTED_CONFIRM_OPERATIONS = frozenset({
    # hub_manage_rule_machine
    "hub_set_rule",
    # hub_manage_backup
    "hub_restore_backup", "hub_delete_backup",
    # hub_manage_radio
    "hub_set_zwave", "hub_set_zigbee", "hub_call_zwave", "hub_call_matter",
    # hub_manage_variables
    "hub_create_variable", "hub_delete_variable",
    "hub_create_connector", "hub_delete_connector",
    # hub_manage_code
    "hub_create_app", "hub_create_driver", "hub_update_app", "hub_update_driver",
    "hub_delete_item", "hub_create_library", "hub_update_library",
    "hub_install_bundle", "hub_delete_bundle",
    # hub_manage_native_rules_and_apps
    "hub_set_native_app", "hub_delete_native_app",
    # hub_manage_destructive_ops
    "hub_reboot", "hub_shutdown", "hub_delete_device", "hub_call_destructive_ops",
    # hub_manage_dashboards
    "hub_delete_dashboard",
    # hub_manage_rooms
    "hub_create_room", "hub_delete_room", "hub_update_room",
    # hub_manage_mcp
    "hub_update_mcp_settings",
    # hub_manage_devices
    "hub_call_device_swap", "hub_call_device_replace", "hub_create_device",
})

DEFAULT_MAX_CONFIRMATION_ACTIONS = 12
SESSION_REQUIRED = (
    "A unique session_id is required before I can queue a sensitive Hubitat "
    "action."
)


class ConfirmationAction(str, Enum):
    """Outcome for one proposed sensitive-action group."""

    BYPASS = "bypass"
    QUEUE = "queue"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class ConfirmationDecision:
    """One deterministic confirmation-policy decision."""

    action: ConfirmationAction
    message: str | None = None


class ConfirmationPolicy:
    """Apply bounded confirmation rules without owning pending state."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        max_actions: int = DEFAULT_MAX_CONFIRMATION_ACTIONS,
    ) -> None:
        self.enabled = bool(enabled)
        self.max_actions = max(1, int(max_actions))

    def requires_confirmation(
        self,
        effect: ToolEffect,
        *,
        declared: bool = True,
    ) -> bool:
        """Confirm only declared calls with a confirmation-bearing effect."""

        return self.enabled and declared and effect.requires_confirmation

    def decide(
        self,
        session_id: str,
        actions: list[tuple[str, dict[str, Any]]],
    ) -> ConfirmationDecision:
        """Validate a sensitive action group and render its queue prompt."""

        if not actions or not self.enabled:
            return ConfirmationDecision(ConfirmationAction.BYPASS)
        if not self.valid_session_id(session_id):
            return ConfirmationDecision(
                ConfirmationAction.REJECT,
                SESSION_REQUIRED,
            )
        if len(actions) > self.max_actions:
            return ConfirmationDecision(
                ConfirmationAction.REJECT,
                (
                    f"This request proposed more than {self.max_actions} sensitive "
                    "actions. Please split it into smaller groups."
                ),
            )
        return ConfirmationDecision(
            ConfirmationAction.QUEUE,
            self.confirmation_prompt(actions),
        )

    @staticmethod
    def valid_session_id(session_id: str) -> bool:
        """Reject the shared default session for queued sensitive actions."""

        normalized = str(session_id).strip()
        return bool(normalized) and normalized != "default"

    @staticmethod
    def confirmation_prompt(
        actions: list[tuple[str, dict[str, Any]]],
    ) -> str:
        """Build stable confirmation wording for one validated group."""

        names = sorted({str(name) for name, _ in actions if str(name)})
        if len(actions) == 1:
            if names == [HUB_UPDATE_FIRMWARE_TOOL]:
                return (
                    "Please confirm before I install the available Hubitat firmware "
                    "update. The hub may restart and be temporarily unavailable."
                )
            name = names[0] if names else "unknown"
            return (
                "Please confirm before I run the sensitive Hubitat action "
                f"`{name}`."
            )
        return (
            f"Please confirm before I run {len(actions)} sensitive Hubitat actions "
            f"through `{', '.join(names)}`."
        )

    @staticmethod
    def unavailable_tools_message(missing: list[str]) -> str:
        """Explain why a queued action was invalidated before execution."""

        names = ", ".join(sorted(set(map(str, missing))))
        return (
            "The queued Hubitat action was cancelled because its tool is no "
            f"longer available: {names}."
        )

    @staticmethod
    def approved_arguments(
        tool_name: str,
        arguments: dict[str, Any],
        *,
        tool_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Translate host approval into the upstream tool's confirm flag.

        Every Hubitat management gateway (``hub_manage_*``) carries its real
        sub-tool call inside a nested ``args`` object -- ``{"tool": ...,
        "args": {...}}`` -- and it is that nested operation's own
        destructive/sensitive handler that requires ``confirm:true``, not the
        gateway call itself. This used to be special-cased to
        ``hub_manage_rule_machine`` only, which meant every other gateway --
        ``hub_manage_backup``, ``hub_manage_radio``, ``hub_manage_variables``,
        ``hub_manage_code``, ``hub_manage_native_rules_and_apps``,
        ``hub_manage_rooms``, ``hub_manage_dashboards``,
        ``hub_manage_destructive_ops``, ``hub_manage_mcp`` -- never actually
        received the approval flag after HomeBrain's own confirmation gate
        approved the call. The user's "yes" would queue and dispatch, but
        Hubitat's own confirm gate would then reject the upstream write for
        lacking ``confirm:true``, silently breaking the confirmation flow for
        a hub-DB restore, a Zwave/Zigbee radio change, a variable delete
        another rule depends on, and app/driver code edits.

        Not every nested operation accepts a confirm field, though -- a
        gateway can mix confirm-bearing and routine operations (e.g.
        ``hub_manage_devices`` has ``hub_call_device_swap``/
        ``hub_create_device`` with their own confirm, but
        ``hub_call_device_command`` has no confirm field at all and instead
        verifies success via ``waitFor``). Injecting confirm into an
        operation that never declared it risks sending an unexpected
        parameter with unverifiable upstream behaviour, so the nested
        operation name is checked against ``_NESTED_CONFIRM_OPERATIONS``, an
        explicit allowlist built by inspecting each gateway's live schema,
        rather than assumed for every nested ``args`` object. Direct
        (non-gateway) tools without a nested ``args`` object still only
        receive the flag when their own declared schema supports it.
        """

        approved = deepcopy(arguments)
        nested = approved.get("args")
        if isinstance(nested, dict):
            nested_operation = str(nested.get("tool") or approved.get("tool") or "")
            if nested_operation in _NESTED_CONFIRM_OPERATIONS:
                nested["confirm"] = True
            return approved
        properties = (
            tool_schema.get("properties", {})
            if isinstance(tool_schema, dict)
            else {}
        )
        if isinstance(properties, dict) and "confirm" in properties:
            approved["confirm"] = True
        return approved


__all__ = [
    "ConfirmationAction",
    "ConfirmationDecision",
    "ConfirmationPolicy",
    "DEFAULT_MAX_CONFIRMATION_ACTIONS",
    "SESSION_REQUIRED",
]
