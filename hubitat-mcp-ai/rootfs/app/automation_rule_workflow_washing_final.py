from __future__ import annotations

from typing import Any, Awaitable, Callable

from automation_rule_workflow import PendingRule, _session_id, _tool_rows
from automation_rule_workflow_live import LiveRuleTool
from automation_rule_workflow_washing import WashingRuleMachineWorkflow


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]


class FinalWashingRuleMachineWorkflow(WashingRuleMachineWorkflow):
    """Final washing workflow with resilient gateway discovery and clear confirmations."""

    async def _find_tool(
        self,
        names: set[str],
        *,
        refresh: bool = False,
    ) -> LiveRuleTool | None:
        """Find direct, mapped or catalogue-only MCP tools.

        Some MCP gateway descriptions are deliberately compact and therefore do not
        enumerate every hidden child tool. The broker's description-derived gateway
        map can consequently omit hub_create_backup even though a management gateway
        advertises it when called in catalogue mode. Probe the live gateway catalogues
        only after the normal direct/mapped lookup has failed.
        """

        found = await super()._find_tool(names, refresh=refresh)
        if found is not None:
            return found

        requested = {str(name).lower() for name in names}
        try:
            visible = await self.client.list_tools(refresh=refresh)
        except Exception:
            return None

        gateways: list[tuple[int, str]] = []
        for tool in visible:
            name = str(getattr(tool, "name", "") or "")
            schema = dict(getattr(tool, "input_schema", {}) or {})
            properties = (
                schema.get("properties")
                if isinstance(schema.get("properties"), dict)
                else {}
            )
            description = str(getattr(tool, "description", "") or "")
            text = f"{name} {description}".lower()
            is_gateway = bool(
                {"tool", "args"}.issubset(properties)
                or name.startswith(("hub_manage_", "manage_", "hub_read_"))
            )
            if not is_gateway:
                continue

            # Probe likely gateways first, while still retaining a complete safe
            # fallback across all catalogue-style gateways.
            tokens = {
                token
                for requested_name in requested
                for token in requested_name.removeprefix("hub_").split("_")
                if len(token) >= 4
            }
            priority = 0 if any(token in text for token in tokens) else 1
            gateways.append((priority, name))

        for _, gateway in sorted(set(gateways)):
            try:
                catalogue = await self.client.call_tool(gateway, {})
            except Exception:
                continue
            if catalogue.is_error:
                continue
            for row in _tool_rows(catalogue.data):
                row_name = str(row.get("name") or "")
                if row_name.lower() not in requested:
                    continue
                return LiveRuleTool(
                    name=row_name,
                    description=str(row.get("description") or ""),
                    schema=dict(row.get("schema") or {}),
                    gateway=gateway,
                )
        return None

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

    async def _create(self, pending: PendingRule) -> dict[str, Any]:
        answer = await super()._create(pending)
        if answer.get("route") == "mcp-rule-preflight-blocked":
            display = answer.get("display")
            if isinstance(display, dict):
                display["note"] = (
                    "HomeBrain checked direct MCP tools and live management-gateway catalogues. "
                    "If backup is still unavailable, enable the backup/admin write tool in the "
                    "Hubitat MCP server, refresh MCP tools, then press Create again."
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
