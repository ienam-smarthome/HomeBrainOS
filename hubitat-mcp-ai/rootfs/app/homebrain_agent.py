from __future__ import annotations

from contextvars import ContextVar
from typing import Any

import mcp_agent_orchestrator as orchestrator
from final_answer_coordinator import FinalAnswerCoordinator
from grounding_policy import GroundingPolicy as BaseGroundingPolicy
from live_evidence_authority import LiveEvidenceAuthority
from mcp_agent_orchestrator import AgentOutcome, UnifiedMCPAgent as BaseUnifiedMCPAgent


_CURRENT_EVIDENCE_RECORDER: ContextVar[Any | None] = ContextVar(
    "homebrain_production_evidence_recorder",
    default=None,
)


class _ProductionGroundingAuthority:
    """GroundingPolicy-compatible adapter for the maintained production agent.

    The orchestrator still constructs its historical ``GroundingPolicy`` name.
    This adapter selects ``LiveEvidenceAuthority`` only while a production-agent
    request has installed its request-local recorder. Direct base-agent callers
    and historical tests retain the original policy contract.
    """

    def __init__(self, *, logs_requested: bool, conversational: bool) -> None:
        recorder = _CURRENT_EVIDENCE_RECORDER.get()
        if recorder is None:
            self._delegate: Any = BaseGroundingPolicy(
                logs_requested=logs_requested,
                conversational=conversational,
            )
        else:
            self._delegate = LiveEvidenceAuthority(
                recorder,
                logs_requested=logs_requested,
                conversational=conversational,
            )

    @staticmethod
    def is_live_log_call(name: str, arguments: dict[str, Any]) -> bool:
        """Preserve the established GroundingPolicy class-level contract."""

        return BaseGroundingPolicy.is_live_log_call(name, arguments)

    @property
    def logs_checked(self) -> bool:
        return bool(self._delegate.logs_checked)

    def record_tool_outcome(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        success: bool,
    ) -> None:
        self._delegate.record_tool_outcome(name, arguments, success=success)

    def decide_no_tool_calls(
        self,
        *,
        has_live_evidence: bool | None = None,
    ) -> Any:
        if isinstance(self._delegate, LiveEvidenceAuthority):
            return self._delegate.decide_no_tool_calls()
        return self._delegate.decide_no_tool_calls(
            has_live_evidence=bool(has_live_evidence)
        )


# Keep the large established tool loop intact while supplying a context-local
# authority at its existing GroundingPolicy construction point.
orchestrator.GroundingPolicy = _ProductionGroundingAuthority


class UnifiedMCPAgent(BaseUnifiedMCPAgent):
    """Production agent with final synthesis and evidence authority delegated."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.final_answers = FinalAnswerCoordinator(self._chat)

    async def _final_answer(self, messages: list[dict[str, Any]]) -> str:
        return await self.final_answers.answer(messages)

    async def _process_user_request(
        self,
        user_prompt: str,
        conversation_history: Any = None,
        *,
        session_id: str = "default",
    ) -> str:
        token = _CURRENT_EVIDENCE_RECORDER.set(self.evidence)
        try:
            return await super()._process_user_request(
                user_prompt,
                conversation_history,
                session_id=session_id,
            )
        finally:
            _CURRENT_EVIDENCE_RECORDER.reset(token)


__all__ = ["AgentOutcome", "UnifiedMCPAgent"]
