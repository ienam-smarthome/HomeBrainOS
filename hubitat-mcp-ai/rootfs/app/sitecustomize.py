"""Production routing backstop for broad performance finalization.

Python imports ``sitecustomize`` automatically from /app. 0.16.65 proved that
ordinary live-read performance turns can return directly from the base
orchestrator without entering FinalAnswerCoordinator. This wrapper keeps the
existing orchestrator untouched while routing any completed turn that already
has successful ``hub_get_performance_stats`` evidence through the shared final
coordinator before the request scope closes.

The wrapper is deliberately evidence-driven rather than prompt-driven. It adds
no work to ordinary requests and it reuses the current request's evidence
recorder/executor, allowing FinalAnswerCoordinator to host-enforce its bounded
recent-log read and deterministic performance semantic validation.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any


_FINALIZER_USED: ContextVar[bool] = ContextVar(
    "homebrain_performance_finalizer_used_01666",
    default=False,
)


def _is_successful_performance_receipt(row: Any) -> bool:
    if not isinstance(row, dict) or row.get("success") is not True:
        return False
    if str(row.get("sub_tool") or "") == "hub_get_performance_stats":
        return True
    arguments = row.get("arguments")
    return (
        isinstance(arguments, dict)
        and str(arguments.get("tool") or "") == "hub_get_performance_stats"
    )


def _install_performance_completion_router() -> None:
    from mcp_agent_orchestrator import UnifiedMCPAgent

    if getattr(UnifiedMCPAgent, "_performance_completion_router_01666", False):
        return

    original_process = UnifiedMCPAgent._process_user_request
    original_final_answer = UnifiedMCPAgent._final_answer

    async def tracked_final_answer(
        self: UnifiedMCPAgent,
        messages: list[dict[str, Any]],
    ) -> str:
        _FINALIZER_USED.set(True)
        return await original_final_answer(self, messages)

    async def routed_process_user_request(
        self: UnifiedMCPAgent,
        user_prompt: str,
        conversation_history: Any = None,
        *,
        session_id: str = "default",
    ) -> str:
        token = _FINALIZER_USED.set(False)
        try:
            answer = await original_process(
                self,
                user_prompt,
                conversation_history,
                session_id=session_id,
            )
            evidence = self.evidence.receipts()
            if not any(
                _is_successful_performance_receipt(row) for row in evidence
            ):
                return answer

            # Some existing stop paths already enter FinalAnswerCoordinator.
            # Track the actual finalizer call request-locally rather than using
            # log presence as a proxy: a provider can itself fetch logs and then
            # still hit the ordinary direct-return branch that caused 0.16.65.
            if _FINALIZER_USED.get():
                return answer

            # Preserve the provider's first-pass analysis as current-turn draft
            # context while forcing the same shared finalizer used by
            # investigative requests. FinalAnswerCoordinator will reuse existing
            # logs when present or add the bounded host log read when missing,
            # then apply evidence-ledger synthesis and semantic validation.
            messages = [
                {"role": "user", "content": str(user_prompt).strip()},
                {"role": "assistant", "content": str(answer)},
            ]
            return await self._final_answer(messages)
        finally:
            _FINALIZER_USED.reset(token)

    UnifiedMCPAgent._final_answer = tracked_final_answer
    UnifiedMCPAgent._process_user_request = routed_process_user_request
    UnifiedMCPAgent._performance_completion_router_01666 = True


def _install_serializer_backstop() -> None:
    import api_response_builder
    from performance_live_semantic_guard import guard_live_performance_semantics

    original = api_response_builder.build_agent_response
    if getattr(original, "_performance_semantic_backstop_01666", False):
        return

    def guarded_build_agent_response(*args: Any, **kwargs: Any) -> dict[str, Any]:
        response = original(*args, **kwargs)
        evidence = response.get("evidence")
        if not isinstance(evidence, list):
            evidence = []
        message, _changed = guard_live_performance_semantics(
            str(response.get("message") or ""),
            evidence,
        )
        response["message"] = message
        return response

    guarded_build_agent_response._performance_semantic_backstop_01666 = True
    api_response_builder.build_agent_response = guarded_build_agent_response


_install_performance_completion_router()
_install_serializer_backstop()
