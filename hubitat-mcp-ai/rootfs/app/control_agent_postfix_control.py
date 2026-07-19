from __future__ import annotations

from typing import Callable

from control_agent_intent import (
    ControlActionIntent,
    ControlIntent,
    ControlIntentInterpreter,
    ControlTargetIntent,
)
from control_postfix_language import parse_postfix_control


def install_postfix_control_intent() -> None:
    """Add target-before-action commands to the deterministic Control Agent parser."""

    if getattr(ControlIntentInterpreter, "_postfix_control_installed", False):
        return

    original: Callable[[str], ControlIntent | None] = (
        ControlIntentInterpreter._deterministic_intent
    )

    def deterministic_with_postfix_control(query: str) -> ControlIntent | None:
        parsed = parse_postfix_control(query)
        if parsed is not None:
            return ControlIntent(
                intent="device_control",
                actions=(
                    ControlActionIntent(
                        command=parsed.action,
                        value=None,
                        target=ControlTargetIntent(
                            name_hint=parsed.name_hint,
                            room_hint=parsed.room_hint,
                            device_type=parsed.device_type,
                            ordinal=parsed.ordinal,
                        ),
                    ),
                ),
                confidence=0.99,
                interpreter="deterministic-control-parser",
            )
        return original(query)

    ControlIntentInterpreter._deterministic_intent = staticmethod(
        deterministic_with_postfix_control
    )
    ControlIntentInterpreter._postfix_control_installed = True


__all__ = ["install_postfix_control_intent"]
