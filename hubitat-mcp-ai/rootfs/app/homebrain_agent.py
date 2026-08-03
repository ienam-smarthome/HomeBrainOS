from __future__ import annotations

import asyncio
import time
from typing import Any

from final_answer_coordinator import FinalAnswerCoordinator
from grounding_policy import (
    reset_grounding_policy_factory,
    set_grounding_policy_factory,
)
from live_evidence_authority import LiveEvidenceAuthority
from mcp_agent_orchestrator import AgentOutcome, UnifiedMCPAgent as BaseUnifiedMCPAgent
from observed_agent_outcome import (
    ObservedAgentOutcome,
    build_observed_agent_outcome,
)
from request_metrics import RequestMetrics
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
        metrics_token = self.request_metrics.begin()
        try:
            outcome = await super().process_user_request_result(
                user_prompt,
                conversation_history,
                session_id=session_id,
            )
            self.request_metrics.increment("tool_calls", len(outcome.evidence))
            if outcome.confirmation_required:
                self.request_metrics.increment("confirmation_queued")
            metrics = self.request_metrics.finish(
                self.request_metrics.completed_outcome()
            )
            return build_observed_agent_outcome(outcome, metrics)
        except asyncio.CancelledError:
            self.request_metrics.increment("request_cancellations")
            self.request_metrics.finish("cancelled")
            raise
        except Exception:
            self.request_metrics.finish("failed")
            raise
        finally:
            self.request_metrics.reset(metrics_token)

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
