"""Ground model claims that a Hubitat capability is unavailable.

The policy inspects only a proposed assistant answer, never the user prompt. It
allows one host-driven discovery recovery and prevents a model from presenting
an unsupported limitation after discovery exposed callable gateways. Tool
execution and registry expansion remain orchestrator/catalog responsibilities.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


CAPABILITY_RETRY_INSTRUCTION = (
    "The previous capability limitation was not grounded. The host searched "
    "using the original request and supplied the structured result below. Use "
    "any newly declared relevant gateway now. Do not repeat an unsupported "
    "capability claim merely because an earlier search used the wrong query or "
    "a similarly named existing item was found. If target identity or supported "
    "arguments are still needed, discover and read them before proposing the "
    "structured mutation."
)
CAPABILITY_ACTION_FAILURE = (
    "I found Hubitat tools relevant to this request, but I could not produce a "
    "valid structured action. No command was sent."
)

_DENIAL_PATTERNS = (
    re.compile(
        r"\b(?:i|homebrain(?:os)?|this (?:assistant|system))\s+"
        r"(?:cannot|can't|am unable to|do not have (?:the )?"
        r"(?:ability|capability) to)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bi can only\b", re.IGNORECASE),
    re.compile(
        r"\b(?:is not supported|is unsupported|does not "
        r"(?:support|expose|advertise))\b",
        re.IGNORECASE,
    ),
)


class CapabilityAction(str, Enum):
    """Decision for one proposed no-tool assistant response."""

    ACCEPT = "accept"
    DISCOVER = "discover"
    REJECT_UNGROUNDED = "reject_ungrounded"


@dataclass(frozen=True, slots=True)
class CapabilityDecision:
    """One deterministic capability-grounding decision."""

    action: CapabilityAction
    message: str | None = None


class CapabilityGroundingPolicy:
    """Allow one original-request discovery before accepting a limitation."""

    def __init__(self) -> None:
        self._recovery_used = False
        self._discovered_gateways = 0

    @staticmethod
    def is_capability_denial(answer: str) -> bool:
        """Recognise explicit assistant claims of missing operational ability."""

        text = str(answer or "").strip()
        return bool(text) and any(pattern.search(text) for pattern in _DENIAL_PATTERNS)

    def record_discovery(self, discovered_gateways: int) -> None:
        """Record how many new known gateways the host recovery exposed."""

        self._discovered_gateways = max(0, int(discovered_gateways))

    def decide(self, answer: str) -> CapabilityDecision:
        """Accept ordinary answers, recover once, or block a false limitation."""

        if not self.is_capability_denial(answer):
            return CapabilityDecision(CapabilityAction.ACCEPT)
        if not self._recovery_used:
            self._recovery_used = True
            return CapabilityDecision(
                CapabilityAction.DISCOVER,
                CAPABILITY_RETRY_INSTRUCTION,
            )
        if self._discovered_gateways:
            return CapabilityDecision(
                CapabilityAction.REJECT_UNGROUNDED,
                CAPABILITY_ACTION_FAILURE,
            )
        return CapabilityDecision(CapabilityAction.ACCEPT)


__all__ = [
    "CAPABILITY_ACTION_FAILURE",
    "CAPABILITY_RETRY_INSTRUCTION",
    "CapabilityAction",
    "CapabilityDecision",
    "CapabilityGroundingPolicy",
]
