from __future__ import annotations

import re
from typing import Callable

from control_agent_capability_filter import install_control_graph_capability_filter
from control_agent_intent import (
    ControlActionIntent,
    ControlIntent,
    ControlIntentInterpreter,
    ControlTargetIntent,
)


_TURN_ON_THEN_LEVEL = re.compile(
    r"^(?:please\s+)?(?:turn|switch)\s+on\s+(?:the\s+)?(.+?)\s+"
    r"(?:to|at)\s+(\d{1,3})\s*(?:%|percent)?[.!?]*$",
    re.IGNORECASE,
)
_TURN_TARGET_ON_THEN_LEVEL = re.compile(
    r"^(?:please\s+)?(?:turn|switch)\s+(?:the\s+)?(.+?)\s+on\s+"
    r"(?:to|at)\s+(\d{1,3})\s*(?:%|percent)?[.!?]*$",
    re.IGNORECASE,
)
# Keep prepositional and bare forms separate. Making `to|at` optional in one
# expression lets the regex engine absorb `at` into the non-greedy device name.
_ABSOLUTE_LEVEL_WITH_PREPOSITION = re.compile(
    r"^(?:please\s+)?(?:set|dim|make)\s+(?:the\s+)?(.+?)\s+"
    r"(?:to|at)\s+(\d{1,3})\s*(?:%|percent)?[.!?]*$",
    re.IGNORECASE,
)
_ABSOLUTE_LEVEL_BARE = re.compile(
    r"^(?:please\s+)?(?:set|dim|make)\s+(?:the\s+)?(.+?)\s+"
    r"(\d{1,3})\s*(?:%|percent)?[.!?]*$",
    re.IGNORECASE,
)
_COMPLEX_TARGET_WORDS = {
    "all",
    "every",
    "except",
    "other",
    "both",
    "them",
    "it",
    "that",
    "those",
    "these",
    "same",
    "back",
    "first",
    "second",
    "third",
    "fourth",
    "fifth",
}
_COMPLEX_TARGET_TERMS = (" if ", " unless ", " when ", " before ", " after ", " and ")
_TRAILING_CONTROL_SYNTAX = re.compile(
    r"(?:\b(?:to|at|percent)\b|\d{1,3}\s*%?)\s*$",
    re.IGNORECASE,
)


def _safe_unique_target(target: str) -> bool:
    normalised = re.sub(r"\s+", " ", str(target or "").strip(" .!?"))
    if not normalised or _TRAILING_CONTROL_SYNTAX.search(normalised):
        return False
    words = set(re.findall(r"[a-z0-9]+", normalised.lower()))
    if not words or words.intersection(_COMPLEX_TARGET_WORDS):
        return False
    padded = f" {normalised.lower()} "
    return not any(term in padded for term in _COMPLEX_TARGET_TERMS)


def _intent(target: str, value_text: str) -> ControlIntent | None:
    try:
        value = float(value_text)
    except Exception:
        return None
    # Never silently clamp a malformed control request. Out-of-range values must
    # fall through to guarded interpretation and cannot be auto-executed.
    if value < 0 or value > 100 or not _safe_unique_target(target):
        return None
    return ControlIntent(
        intent="device_control",
        actions=(
            ControlActionIntent(
                command="set_level",
                value=value,
                target=ControlTargetIntent(name_hint=target.strip()),
            ),
        ),
        confidence=0.99,
        interpreter="deterministic-control-parser",
    )


def install_combined_level_intent() -> None:
    """Install Control Agent language and actuable-device graph safeguards.

    This must run before ``HomeBrainControlAgent`` is constructed. It restricts
    the graph to devices with live control evidence, then wraps the existing
    static parser so combined and absolute level phrases become one clean
    ``setLevel`` action without leaking prepositions into device names.
    """

    install_control_graph_capability_filter()
    if getattr(ControlIntentInterpreter, "_combined_level_installed", False):
        return

    original: Callable[[str], ControlIntent | None] = (
        ControlIntentInterpreter._deterministic_intent
    )

    def deterministic_with_combined_level(query: str) -> ControlIntent | None:
        text = str(query or "").strip()
        for pattern in (_TURN_ON_THEN_LEVEL, _TURN_TARGET_ON_THEN_LEVEL):
            match = pattern.match(text)
            if match:
                return _intent(match.group(1), match.group(2))

        # Parse valid absolute-level commands here instead of handing them to the
        # older optional-preposition expression. Ordered patterns guarantee that
        # `at` and `to` are consumed as grammar, never as part of the device label.
        for pattern in (
            _ABSOLUTE_LEVEL_WITH_PREPOSITION,
            _ABSOLUTE_LEVEL_BARE,
        ):
            match = pattern.match(text)
            if match:
                return _intent(match.group(1), match.group(2))

        return original(query)

    ControlIntentInterpreter._deterministic_intent = staticmethod(
        deterministic_with_combined_level
    )
    ControlIntentInterpreter._combined_level_installed = True


__all__ = ["install_combined_level_intent"]
