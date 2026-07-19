from __future__ import annotations

from typing import Any, Awaitable, Callable

from automation_rule_workflow import _session_id
from automation_rule_workflow_backup_filename_safe import (
    FilenameSafeBackupWashingRuleMachineWorkflow,
)
from mcp_client import MCPToolResult


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]
_NATIVE_WRITE_NAMES = {
    "hub_set_rule",
    "set_rule",
    "hub_set_rule_paused",
    "set_rule_paused",
}
_RULE_GATEWAY_NAMES = (
    "hub_manage_rule_machine",
    "hub_manage_native_rules_and_apps",
)


def _redacted(arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        str(key): ("<present>" if "key" in str(key).lower() else value)
        for key, value in arguments.items()
    }


def _error_text(exc: Exception) -> str:
    message = str(exc).strip()
    return message or type(exc).__name__


class WriteSafeBackupWashingRuleMachineWorkflow(
    FilenameSafeBackupWashingRuleMachineWorkflow
):
    """Keep native Rule Machine HTTP errors inside structured HomeBrain results.

    MCP Rule Server can expose native writes directly or through a category
    gateway. A transient/stale route can return HTTP 500 before the tool result is
    encoded. All create/update calls carry stable operation tokens, so retrying
    the same arguments through the alternate advertised route is idempotent.
    """

    async def _call_rule_tool(self, tool: Any, arguments: dict[str, Any]):
        name = str(getattr(tool, "name", "") or "")
        if name not in _NATIVE_WRITE_NAMES:
            return await super()._call_rule_tool(tool, arguments)

        attempts: list[dict[str, Any]] = []
        primary_gateway = str(getattr(tool, "gateway", "") or "") or None
        try:
            return await super()._call_rule_tool(tool, arguments)
        except Exception as exc:
            attempts.append(
                {
                    "route": primary_gateway or "direct",
                    "exception_type": type(exc).__name__,
                    "error": _error_text(exc),
                }
            )

        visible_names: set[str] = set()
        try:
            visible_names = {
                str(getattr(item, "name", "") or "")
                for item in await self.client.list_tools(refresh=True)
            }
        except Exception as exc:
            attempts.append(
                {
                    "route": "tools/list",
                    "exception_type": type(exc).__name__,
                    "error": _error_text(exc),
                }
            )

        alternatives: list[tuple[str, dict[str, Any]]] = []
        if primary_gateway:
            if name in visible_names:
                alternatives.append((name, dict(arguments)))
        else:
            for gateway in _RULE_GATEWAY_NAMES:
                if gateway in visible_names:
                    alternatives.append(
                        (gateway, {"tool": name, "args": dict(arguments)})
                    )

        for request_name, request_args in alternatives:
            try:
                result = await self.client.call_tool(request_name, request_args)
                result.raw.setdefault(
                    "homebrain_write_route_recovery",
                    {
                        "primary": primary_gateway or "direct",
                        "recovered_via": request_name,
                    },
                )
                return result
            except Exception as exc:
                attempts.append(
                    {
                        "route": request_name,
                        "exception_type": type(exc).__name__,
                        "error": _error_text(exc),
                    }
                )

        summary = "; ".join(
            f"{item['route']}: {item['exception_type']}: {item['error']}"
            for item in attempts
        )
        message = (
            f"Native Rule Machine write '{name}' failed before Hubitat returned a "
            f"tool result. {summary}"
        )
        data = {
            "success": False,
            "error": message,
            "exceptionType": attempts[-1]["exception_type"] if attempts else "MCPError",
            "writeTool": name,
            "primaryGateway": primary_gateway,
            "alternateRouteAttempted": len(alternatives) > 0,
            "attempts": attempts,
            "arguments": _redacted(dict(arguments)),
        }
        return MCPToolResult(
            name=name,
            arguments=dict(arguments),
            raw={"isError": True, "homebrain": data},
            text=message,
            data=data,
            is_error=True,
        )


def install_write_safe_backup_rule_machine_workflow(
    application: Any,
    device_index: Any,
    *,
    ttl_seconds: float = 600.0,
    max_sessions: int = 128,
    write_enabled: bool = True,
    require_paused_create: bool = True,
) -> WriteSafeBackupWashingRuleMachineWorkflow:
    original_ask: AskHandler = application.ask
    service = WriteSafeBackupWashingRuleMachineWorkflow(
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
    "WriteSafeBackupWashingRuleMachineWorkflow",
    "install_write_safe_backup_rule_machine_workflow",
]
