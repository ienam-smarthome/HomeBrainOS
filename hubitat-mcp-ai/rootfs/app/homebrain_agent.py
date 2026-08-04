from __future__ import annotations

import time
from typing import Any

from final_answer_coordinator import FinalAnswerCoordinator
from grounding_policy import (
    reset_grounding_policy_factory,
    set_grounding_policy_factory,
)
from live_evidence_authority import LiveEvidenceAuthority
from mcp_agent_orchestrator import AgentOutcome, UnifiedMCPAgent as BaseUnifiedMCPAgent
from observed_agent_outcome import ObservedAgentOutcome
from request_metrics import RequestMetrics
from request_observation import RequestObservationCoordinator
from token_aware_context_policy import TokenAwareModelContextPolicy


class UnifiedMCPAgent(BaseUnifiedMCPAgent):
    """Production agent with delegated synthesis, grounding, and observability."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.context_policy = TokenAwareModelContextPolicy(
            model_name=self.model_name,
            max_history_messages=self.context_policy.max_history_messages,
            max_history_chars=self.context_policy.max_history_chars,
            max_tool_context_chars=self.context_policy.max_tool_context_chars,
            compacted_tool_result_chars=self.context_policy.compacted_tool_result_chars,
        )
        self.max_history_messages = self.context_policy.max_history_messages
        self.max_history_chars = self.context_policy.max_history_chars
        self.max_tool_context_chars = self.context_policy.max_tool_context_chars
        self.compacted_tool_result_chars = self.context_policy.compacted_tool_result_chars
        self.final_answers = FinalAnswerCoordinator(self._chat)
        self.request_metrics = RequestMetrics()
        self.request_observation = RequestObservationCoordinator(self.request_metrics)

    async def _chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        started = time.monotonic()
        self.request_metrics.increment("model_rounds")
        try:
            return await super()._chat(messages, tools)
        finally:
            self.request_metrics.observe_ms(
                "provider",
                (time.monotonic() - started) * 1000,
            )

    async def _final_answer(self, messages: list[dict[str, Any]]) -> str:
        return await self.final_answers.answer(messages)

    def _create_grounding_policy(
        self,
        *,
        logs_requested: bool,
        conversational: bool,
    ) -> LiveEvidenceAuthority:
        """Create the production request's evidence-aware grounding authority."""

        return LiveEvidenceAuthority(
            self.evidence,
            logs_requested=logs_requested,
            conversational=conversational,
            record_metric=self.request_metrics.increment,
        )

    async def process_user_request_result(
        self,
        user_prompt: str,
        conversation_history: Any = None,
        *,
        session_id: str = "default",
    ) -> ObservedAgentOutcome:
        base_process = super().process_user_request_result
        return await self.request_observation.run(
            lambda: base_process(
                user_prompt,
                conversation_history,
                session_id=session_id,
            )
        )

    async def _process_user_request(
        self,
        user_prompt: str,
        conversation_history: Any = None,
        *,
        session_id: str = "default",
    ) -> str:
        factory_token = set_grounding_policy_factory(
            self._create_grounding_policy
        )
        try:
            return await super()._process_user_request(
                user_prompt,
                conversation_history,
                session_id=session_id,
            )
        finally:
            reset_grounding_policy_factory(factory_token)


__all__ = ["AgentOutcome", "ObservedAgentOutcome", "UnifiedMCPAgent"]
