from __future__ import annotations

from typing import Any, Awaitable, Callable

from automation_rule_workflow import _session_id
from automation_rule_workflow_live import LiveSchemaAutomationRuleWorkflow


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]


class ReleaseAutomationRuleWorkflow(LiveSchemaAutomationRuleWorkflow):
    """Release wrapper with visible safety reasons and write invalidation."""

    async def remember_answer(self, session_id: str, answer: dict[str, Any]) -> None:
        recommendation = answer.get("recommendation")
        if isinstance(recommendation, dict) and recommendation.get("type") == "cold-storage-door":
            previous_action = str(recommendation.get("action") or "")
            supported_action = (
                "Send a notification through one selected Hubitat Notification device, "
                "then repeat once after 5 minutes if the contact is still open."
            )
            supported_safeguard = (
                "Cancel the pending repeat immediately when the contact closes."
            )
            recommendation["action"] = supported_action
            recommendation["safeguard"] = supported_safeguard
            message = str(answer.get("message") or "")
            if previous_action and previous_action in message:
                answer["message"] = message.replace(previous_action, supported_action)
            display = answer.get("display")
            if isinstance(display, dict):
                items = display.get("items")
                if isinstance(items, list):
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        title = str(item.get("title") or "").lower()
                        if title == "action":
                            item["subtitle"] = supported_action
                        elif title == "safeguard":
                            item["subtitle"] = supported_safeguard
                summary = str(display.get("summary") or "")
                if previous_action and previous_action in summary:
                    display["summary"] = summary.replace(previous_action, supported_action)
        await super().remember_answer(session_id, answer)

    async def _build(self, pending):
        answer = await super()._build(pending)
        display = answer.get("display")
        if isinstance(display, dict):
            display["summary"] = answer.get("message")
            unresolved = (answer.get("rule_draft") or {}).get("unresolved") or []
            if unresolved:
                display["note"] = " ".join(str(item) for item in unresolved)
        return answer

    async def _call_rule_tool(self, tool, arguments):
        result = await super()._call_rule_tool(tool, arguments)
        if result.is_error:
            return result
        name = str(getattr(tool, "name", "") or "").lower()
        unprefixed = name[4:] if name.startswith("hub_") else name
        changes_rule = unprefixed.startswith(
            (
                "create_rule",
                "create_visual_rule",
                "update_rule",
                "pause_rule",
                "resume_rule",
                "enable_rule",
                "disable_rule",
                "set_rule",
            )
        )
        if changes_rule and hasattr(self.client, "invalidate"):
            try:
                await self.client.invalidate("catalog")
            except Exception:
                # A successful Hubitat write must not be turned into a failure by
                # optional local cache invalidation.
                pass
        return result


def install_release_automation_rule_workflow(
    application: Any,
    device_index: Any,
    *,
    ttl_seconds: float = 600.0,
    max_sessions: int = 128,
    write_enabled: bool = True,
    require_paused_create: bool = True,
) -> ReleaseAutomationRuleWorkflow:
    original_ask: AskHandler = application.ask
    service = ReleaseAutomationRuleWorkflow(
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
    "ReleaseAutomationRuleWorkflow",
    "install_release_automation_rule_workflow",
]
