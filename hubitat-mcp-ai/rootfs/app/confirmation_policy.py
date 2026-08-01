"""Pure confirmation decisions for structured Hubitat tool calls.

The policy decides whether an already-classified call needs confirmation,
validates a proposed confirmation group, and builds deterministic user-facing
wording. It never stores pending actions, consumes confirmation replies, or
executes tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from tool_registry import ToolEffect


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
            if names == ["hub_update_firmware"]:
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


__all__ = [
    "ConfirmationAction",
    "ConfirmationDecision",
    "ConfirmationPolicy",
    "DEFAULT_MAX_CONFIRMATION_ACTIONS",
    "SESSION_REQUIRED",
]
