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

from typing import Any


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

    original = UnifiedMCPAgent._process_user_request

    async def routed_process_user_request(
        self: UnifiedMCPAgent,
        user_prompt: str,
        conversation_history: Any = None,
        *,
        session_id: str = "default",
    ) -> str:
        answer = await original(
            self,
            user_prompt,
            conversation_history,
            session_id=session_id,
        )
        evidence = self.evidence.receipts()
        if not any(_is_successful_performance_receipt(row) for row in evidence):
            return answer

        # If the base orchestrator already used FinalAnswerCoordinator, its
        # host-enforced log evidence/counter will be present and a second final
        # synthesis would only duplicate work.
        if any(
            isinstance(row, dict)
            and row.get("success") is True
            and str(row.get("sub_tool") or "") == "hub_get_logs"
            for row in evidence
        ):
            return answer

        # Preserve the provider's first-pass analysis as current-turn draft
        # context while forcing the same shared finalizer used by investigative
        # requests. FinalAnswerCoordinator will add the bounded host log read,
        # evidence ledger, semantic validation, and repair pass as needed.
        messages = [
            {"role": "user", "content": str(user_prompt).strip()},
            {"role": "assistant", "content": str(answer)},
        ]
        return await self._final_answer(messages)

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
