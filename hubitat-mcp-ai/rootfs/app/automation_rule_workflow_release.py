from __future__ import annotations

from typing import Any, Awaitable, Callable

import automation_rule_workflow_live as live_module
from automation_rule_workflow import _normalise, _session_id
from automation_rule_workflow_live import LiveSchemaAutomationRuleWorkflow
from device_intelligence_catalogue import _capability_names


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]


def _strict_notification_device(item: dict[str, Any]) -> bool:
    """Accept only devices that can receive Hubitat notification actions.

    Speech-synthesis devices are intentionally excluded: ``send_notification``
    requires a Notification-capable target and must not silently become text to
    speech on a speaker. Custom notification drivers remain supported when they
    expose a recognised notification command.
    """
    capabilities = {
        _normalise(name).replace(" ", "")
        for name in _capability_names(item)
    }
    commands: set[str] = set()
    for key in ("supportedCommands", "commands"):
        value = item.get(key)
        if isinstance(value, str):
            commands.add(value)
        elif isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    name = entry.get("name") or entry.get("command")
                    if name:
                        commands.add(str(name))
                elif entry not in (None, ""):
                    commands.add(str(entry))
        elif isinstance(value, dict):
            commands.update(str(name) for name in value)
    commands = {_normalise(name).replace(" ", "") for name in commands}
    return bool(
        capabilities.intersection(
            {
                "notification",
                "devicenotification",
                "pushnotification",
            }
        )
        or commands.intersection(
            {
                "devicenotification",
                "sendnotification",
                "notify",
            }
        )
    )


# LiveSchemaAutomationRuleWorkflow resolves this module global when compiling a
# draft. Tighten it for the release without duplicating the full compiler.
live_module._is_notification_device = _strict_notification_device


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

    async def _create(self, pending):
        answer = await super()._create(pending)
        if not answer.get("success") or pending.created_rule is None:
            return answer

        # Some MCP releases confirm creation but omit the child app/rule ID from
        # the create response. Resolve the exact new name immediately so Dry-run,
        # Enable and Disable never send a rule name where the schema requires ID.
        if not str(pending.created_rule.get("id") or "").strip():
            draft_name = str((pending.draft or {}).get("name") or "").strip()
            resolved = await self._existing_rule(draft_name) if draft_name else None
            if resolved and resolved.get("id"):
                pending.created_rule.update(resolved)
                answer["created_rule"] = dict(pending.created_rule)
                answer["display"] = self._created_display(pending)
                technical = answer.get("technical")
                if isinstance(technical, dict):
                    technical["created_rule_id_resolved_by_name"] = True
            else:
                pending.stage = "created"
                warning = (
                    "The rule was created, but Hubitat did not return its ID and an exact "
                    "name lookup could not resolve it. Review the rule in Hubitat before "
                    "testing or enabling it."
                )
                pending.created_rule["warning"] = warning
                answer["message"] = str(answer.get("message") or "") + " " + warning
                display = answer.get("display")
                if isinstance(display, dict):
                    display["actions"] = []
                    display["note"] = warning
        return answer

    async def _operate(self, pending, operation: str):
        if pending.created_rule is not None and not str(
            pending.created_rule.get("id") or ""
        ).strip():
            return self._wrong_stage(
                "The created rule ID could not be verified. Review it in Hubitat before testing or enabling it."
            )
        return await super()._operate(pending, operation)

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
