from __future__ import annotations

from typing import Any, Awaitable, Callable

from automation_rule_workflow import PendingRule, _session_id
from automation_rule_workflow_washing import WashingRuleMachineWorkflow


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]


class FinalWashingRuleMachineWorkflow(WashingRuleMachineWorkflow):
    """Final washing workflow with device-specific operation confirmations."""

    async def _call_operation(
        self,
        pending: PendingRule,
        operation: str,
    ) -> dict[str, Any]:
        answer = await super()._call_operation(pending, operation)
        is_washing = str((pending.draft or {}).get("type") or "") == "washing-complete"
        if is_washing and operation == "enable" and answer.get("success") is True:
            title = str((pending.created_rule or {}).get("name") or "Washing machine rule")
            answer["message"] = (
                f"Enabled **{title}**. It can now monitor washing-machine power and notify "
                "the selected phone after a genuine cycle finishes."
            )
        return answer


def install_final_washing_rule_machine_workflow(
    application: Any,
    device_index: Any,
    *,
    ttl_seconds: float = 600.0,
    max_sessions: int = 128,
    write_enabled: bool = True,
    require_paused_create: bool = True,
) -> FinalWashingRuleMachineWorkflow:
    original_ask: AskHandler = application.ask
    service = FinalWashingRuleMachineWorkflow(
        application,
        device_index,
        ttl_seconds=ttl_seconds,
        max_sessions=max_sessions,
        write_enabled=write_enabled,
        require_paused_create=require_paused_create,
    )

    async def ask_with_rule_workflow(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "").strip()
        command = service.command(query)
        if command:
            answer = await service.handle(request, command)
            answer.setdefault("version", application.VERSION)
            return answer
        answer = await original_ask(request)
        await service.remember_answer(_session_id(request), answer)
        return answer

    application.ask = ask_with_rule_workflow
    application.automation_rule_workflow = service
    return service


__all__ = [
    "FinalWashingRuleMachineWorkflow",
    "install_final_washing_rule_machine_workflow",
]
