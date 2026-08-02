from __future__ import annotations

import asyncio
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

import mcp_agent_orchestrator as orchestrator
from final_answer_coordinator import FinalAnswerCoordinator
from grounding_policy import GroundingPolicy as BaseGroundingPolicy
from live_evidence_authority import LiveEvidenceAuthority
from mcp_agent_orchestrator import AgentOutcome, UnifiedMCPAgent as BaseUnifiedMCPAgent
from request_metrics import RequestMetrics
from token_aware_context_policy import TokenAwareModelContextPolicy


_CURRENT_PRODUCTION_CONTEXT: ContextVar[tuple[Any, RequestMetrics] | None] = ContextVar(
    "homebrain_production_grounding_context",
    default=None,
)


@dataclass(slots=True)
class ObservedAgentOutcome(AgentOutcome):
    """Agent result with a privacy-safe, request-local metrics snapshot."""

    metrics: dict[str, Any] = field(default_factory=dict)


class _ProductionGroundingAuthority:
    """GroundingPolicy-compatible adapter for the maintained production agent."""

    def __init__(self, *, logs_requested: bool, conversational: bool) -> None:
        context = _CURRENT_PRODUCTION_CONTEXT.get()
        if context is None:
            self._delegate: Any = BaseGroundingPolicy(
                logs_requested=logs_requested,
                conversational=conversational,
            )
        else:
            recorder, metrics = context
            self._delegate = LiveEvidenceAuthority(
                recorder,
                logs_requested=logs_requested,
                conversational=conversational,
                record_metric=metrics.increment,
            )

    @staticmethod
    def is_live_log_call(name: str, arguments: dict[str, Any]) -> bool:
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


orchestrator.GroundingPolicy = _ProductionGroundingAuthority


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
            metrics = self.request_metrics.finish("success")
            return ObservedAgentOutcome(
                message=outcome.message,
                request_class=outcome.request_class,
                evidence=outcome.evidence,
                choices=outcome.choices,
                confirmation_required=outcome.confirmation_required,
                confirmation_count=outcome.confirmation_count,
                metrics=metrics,
            )
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
        token = _CURRENT_PRODUCTION_CONTEXT.set((self.evidence, self.request_metrics))
        try:
            return await super()._process_user_request(
                user_prompt,
                conversation_history,
                session_id=session_id,
            )
        finally:
            _CURRENT_PRODUCTION_CONTEXT.reset(token)


__all__ = ["AgentOutcome", "ObservedAgentOutcome", "UnifiedMCPAgent"]
