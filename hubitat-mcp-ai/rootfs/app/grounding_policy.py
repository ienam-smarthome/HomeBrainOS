"""Request-local retry and refusal policy for grounded Hubitat answers.

The policy owns the small state machine used when the model tries to answer
without calling a tool. It does not inspect prompt text, execute tools, or
decide whether an evidence receipt is authoritative; the orchestrator supplies
those already-resolved facts.
"""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar, Token
from dataclasses import dataclass
from enum import Enum
from typing import Any


LOG_RETRY_INSTRUCTION = (
    "Do not answer yet. Fetch the actual logs now by calling "
    "hub_read_diagnostics with tool='hub_get_logs' and "
    "args={'since':'30m','limit':100}, then summarize only that result."
)
LOG_REFUSAL = (
    "I could not retrieve the actual Hubitat logs, so I will not provide an "
    "inferred log summary."
)
EVIDENCE_RETRY_INSTRUCTION = (
    "Do not answer from memory or inference. No successful live evidence "
    "receipt exists yet. Call the most relevant declared Hubitat read tool "
    "now, then answer only from its result. Tool discovery alone is not evidence."
)
EVIDENCE_REFUSAL = (
    "I could not retrieve verified live Hubitat evidence, so I will not "
    "provide an inferred answer."
)


class GroundingAction(str, Enum):
    """Outcome when the model returns an answer without tool calls."""

    ACCEPT = "accept"
    RETRY = "retry"
    REFUSE = "refuse"


@dataclass(frozen=True, slots=True)
class GroundingDecision:
    """One deterministic response-policy decision."""

    action: GroundingAction
    message: str | None = None


GroundingPolicyFactory = Callable[..., Any]
_ACTIVE_GROUNDING_POLICY_FACTORY: ContextVar[GroundingPolicyFactory | None] = (
    ContextVar("homebrain_grounding_policy_factory", default=None)
)


def set_grounding_policy_factory(factory: GroundingPolicyFactory) -> Token:
    """Install one request-local policy factory and return its reset token."""

    return _ACTIVE_GROUNDING_POLICY_FACTORY.set(factory)


def reset_grounding_policy_factory(token: Token) -> None:
    """Restore the previous request-local policy factory."""

    _ACTIVE_GROUNDING_POLICY_FACTORY.reset(token)


class GroundingPolicy:
    """Track one request's bounded grounding retries and log evidence."""

    def __new__(
        cls,
        *,
        logs_requested: bool,
        conversational: bool,
    ) -> Any:
        if cls is GroundingPolicy:
            factory = _ACTIVE_GROUNDING_POLICY_FACTORY.get()
            if factory is not None:
                return factory(
                    logs_requested=logs_requested,
                    conversational=conversational,
                )
        return super().__new__(cls)

    def __init__(self, *, logs_requested: bool, conversational: bool) -> None:
        self.logs_requested = bool(logs_requested)
        self.conversational = bool(conversational)
        self.logs_checked = False
        self._log_retry_used = False
        self._evidence_retry_used = False

    @classmethod
    def default(
        cls,
        *,
        logs_requested: bool,
        conversational: bool,
    ) -> "GroundingPolicy":
        """Construct the built-in policy even when a request override is active."""

        token = _ACTIVE_GROUNDING_POLICY_FACTORY.set(None)
        try:
            return cls(
                logs_requested=logs_requested,
                conversational=conversational,
            )
        finally:
            _ACTIVE_GROUNDING_POLICY_FACTORY.reset(token)

    @staticmethod
    def is_live_log_call(name: str, arguments: dict[str, Any]) -> bool:
        """Recognise only the authoritative diagnostics log sub-tool."""

        return (
            name == "hub_read_diagnostics"
            and str(arguments.get("tool") or "") == "hub_get_logs"
        )

    def record_tool_outcome(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        success: bool,
    ) -> None:
        """Observe an executed call without treating unrelated tools as logs."""

        if self.is_live_log_call(name, arguments):
            # Latch, don't overwrite: a later failed or duplicate log fetch
            # in the same request must not un-satisfy log evidence a prior
            # call in this same turn already recorded successfully. Once
            # true, this stays true for the life of the request -- exactly
            # mirroring _evidence_retry_used/_log_retry_used, which are
            # also one-way latches on this same policy object.
            self.logs_checked = self.logs_checked or bool(success)

    def decide_no_tool_calls(self, *, has_live_evidence: bool) -> GroundingDecision:
        """Accept, retry once, or refuse when the model emits no tool calls."""

        if self.logs_requested and not self.logs_checked:
            if not self._log_retry_used:
                self._log_retry_used = True
                return GroundingDecision(
                    GroundingAction.RETRY,
                    LOG_RETRY_INSTRUCTION,
                )
            return GroundingDecision(GroundingAction.REFUSE, LOG_REFUSAL)

        if not self.conversational and not has_live_evidence:
            if not self._evidence_retry_used:
                self._evidence_retry_used = True
                return GroundingDecision(
                    GroundingAction.RETRY,
                    EVIDENCE_RETRY_INSTRUCTION,
                )
            return GroundingDecision(GroundingAction.REFUSE, EVIDENCE_REFUSAL)

        return GroundingDecision(GroundingAction.ACCEPT)


__all__ = [
    "EVIDENCE_REFUSAL",
    "EVIDENCE_RETRY_INSTRUCTION",
    "GroundingAction",
    "GroundingDecision",
    "GroundingPolicy",
    "GroundingPolicyFactory",
    "LOG_REFUSAL",
    "LOG_RETRY_INSTRUCTION",
    "reset_grounding_policy_factory",
    "set_grounding_policy_factory",
]
