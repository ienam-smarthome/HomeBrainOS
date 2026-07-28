from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import types

from mcp_client import HubitatMCPClient, MCPTool, MCPToolResult

logger = logging.getLogger("HomeBrainOS.Orchestrator")

_CONFIRM_WORDS = {"confirm", "confirmed", "proceed", "yes", "yes proceed", "do it"}
_SENSITIVE_TERMS = {
    "backup", "delete", "disable", "enable", "factory_reset", "firmware",
    "garage", "lock", "reboot", "restart", "rule", "security", "shutdown", "unlock",
}


@dataclass(slots=True)
class PendingConfirmation:
    expires_at: float
    tool_name: str
    arguments: dict[str, Any]
    contents: list[types.Content]
    model_content: types.Content


class UnifiedMCPAgent:
    """Gemini SDK agent that executes live Hubitat MCP function declarations."""

    def __init__(
        self,
        mcp_client: HubitatMCPClient,
        gemini_api_key: str,
        model_name: str = "gemini-3.6-flash",
        *,
        gemini_base_url: str = "https://generativelanguage.googleapis.com",
        timeout_seconds: float = 15,
        tool_limit: int = 48,
        max_tool_rounds: int = 6,
        require_sensitive_confirmation: bool = True,
        confirmation_ttl_seconds: float = 120,
        ai_client: Any | None = None,
    ) -> None:
        self.mcp = mcp_client
        self.api_key = str(gemini_api_key or "").strip()
        self.model_name = str(model_name or "").strip()
        self.tool_limit = max(1, int(tool_limit))
        self.max_tool_rounds = max(1, int(max_tool_rounds))
        self.require_sensitive_confirmation = bool(require_sensitive_confirmation)
        self.confirmation_ttl_seconds = max(10.0, float(confirmation_ttl_seconds))
        self._pending: dict[str, PendingConfirmation] = {}
        self._client_options = (gemini_base_url, timeout_seconds)
        if ai_client is not None:
            self.ai_client = ai_client
        else:
            self.ai_client = None

    def _ensure_client(self) -> Any:
        if self.ai_client is not None:
            return self.ai_client
        if not self.api_key:
            raise RuntimeError("Gemini API key is not configured")
        gemini_base_url, timeout_seconds = self._client_options
        base_url = str(gemini_base_url or "").rstrip("/")
        if base_url.endswith("/v1beta"):
            base_url = base_url[: -len("/v1beta")]
        self.ai_client = genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(
                base_url=base_url or None,
                api_version="v1beta",
                timeout=int(max(3.0, float(timeout_seconds)) * 1000),
            ),
        )
        return self.ai_client

    async def close(self) -> None:
        close = getattr(getattr(self.ai_client, "aio", None), "aclose", None)
        if callable(close):
            await close()

    async def _build_system_instruction(self) -> str:
        rows: list[str] = []
        try:
            for device in await self.mcp.get_cached_devices():
                label = device.get("label") or device.get("name") or "Unknown device"
                device_id = device.get("id") or device.get("deviceId")
                room = device.get("room") or device.get("roomName") or "Unassigned"
                capabilities = device.get("capabilities") or []
                if isinstance(capabilities, dict):
                    capabilities = list(capabilities)
                if not isinstance(capabilities, list):
                    capabilities = [capabilities]
                rows.append(
                    f"- {label!r} | ID: {device_id} | Room: {room} | "
                    f"Capabilities: {', '.join(map(str, capabilities)) or 'unknown'}"
                )
        except Exception as exc:
            logger.warning("Could not build the live device manifest: %s", exc)
        manifest = "\n".join(rows) or "No live device manifest is currently available."
        return (
            "You are HomeBrainOS, a concise smart-home assistant. Use Hubitat MCP functions "
            "for every live state claim and action. Match informal names against the live "
            "manifest and use exact IDs whenever possible. Never invent devices, states, "
            "tool results, or successful actions. Ask one short question when a target is "
            "genuinely ambiguous. Sensitive calls are confirmed and enforced by the host.\n\n"
            f"LIVE DEVICE MANIFEST\n{manifest}"
        )

    @staticmethod
    def _tool_declaration(tool: MCPTool) -> types.FunctionDeclaration:
        schema = tool.input_schema if isinstance(tool.input_schema, dict) else {}
        return types.FunctionDeclaration(
            name=tool.name,
            description=tool.description or tool.name,
            parameters_json_schema=schema or {"type": "object", "properties": {}},
        )

    @staticmethod
    def _normalise_history(history: Any) -> list[types.Content]:
        contents: list[types.Content] = []
        for item in list(history or [])[-20:]:
            if hasattr(item, "model_dump"):
                item = item.model_dump()
            if not isinstance(item, dict):
                continue
            role = "model" if item.get("role") in {"assistant", "model"} else "user"
            text = item.get("content") or item.get("text")
            if text:
                contents.append(types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=str(text))],
                ))
        return contents

    @staticmethod
    def _result_payload(result: MCPToolResult) -> dict[str, Any]:
        if result.is_error:
            return {"error": result.text or "MCP tool failed"}
        return {"result": result.data if result.data is not None else result.text}

    @staticmethod
    def _is_sensitive(tool: MCPTool) -> bool:
        if (tool.annotations or {}).get("destructiveHint") is True:
            return True
        name = tool.name.lower().replace("-", "_")
        return any(term in name for term in _SENSITIVE_TERMS)

    def _take_confirmation(self, session_id: str, prompt: str) -> PendingConfirmation | None:
        pending = self._pending.get(session_id)
        if not pending:
            return None
        if pending.expires_at <= time.monotonic():
            self._pending.pop(session_id, None)
            return None
        if " ".join(prompt.strip().lower().split()) not in _CONFIRM_WORDS:
            return None
        self._pending.pop(session_id, None)
        return pending

    async def _generate(
        self,
        contents: list[types.Content],
        *,
        instruction: str,
        tool: types.Tool | None,
    ) -> Any:
        client = self._ensure_client()
        return await client.aio.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=instruction,
                tools=[tool] if tool else None,
                temperature=0.1,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )

    async def _resume_confirmation(
        self,
        pending: PendingConfirmation,
        *,
        instruction: str,
        tool: types.Tool | None,
    ) -> str:
        try:
            result = await self.mcp.call_tool(pending.tool_name, pending.arguments)
            payload = self._result_payload(result)
        except Exception as exc:
            payload = {"error": str(exc)}
        contents = [*pending.contents, pending.model_content, types.Content(
            role="tool",
            parts=[types.Part.from_function_response(
                name=pending.tool_name,
                response=payload,
            )],
        )]
        response = await self._generate(contents, instruction=instruction, tool=tool)
        return response.text or "Confirmed command completed."

    async def process_user_request(
        self,
        user_prompt: str,
        conversation_history: Any = None,
        *,
        session_id: str = "default",
    ) -> str:
        tools = (await self.mcp.list_tools())[: self.tool_limit]
        tool_by_name = {tool.name: tool for tool in tools}
        sdk_tool = types.Tool(
            function_declarations=[self._tool_declaration(item) for item in tools]
        ) if tools else None
        instruction = await self._build_system_instruction()
        pending = self._take_confirmation(session_id, user_prompt)
        if pending:
            return await self._resume_confirmation(
                pending, instruction=instruction, tool=sdk_tool
            )

        contents = self._normalise_history(conversation_history)
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=str(user_prompt).strip())],
        ))
        for _ in range(self.max_tool_rounds):
            response = await self._generate(contents, instruction=instruction, tool=sdk_tool)
            calls = list(response.function_calls or [])
            if not calls:
                return response.text or "Done."
            model_content = response.candidates[0].content
            sensitive_calls = [
                call
                for call in calls
                if (declared := tool_by_name.get(str(call.name or ""))) is not None
                and self.require_sensitive_confirmation
                and self._is_sensitive(declared)
            ]
            if sensitive_calls:
                if session_id == "default":
                    return (
                        "A unique session_id is required before I can queue a sensitive "
                        "Hubitat action for confirmation."
                    )
                if len(sensitive_calls) > 1:
                    return (
                        "This request proposed multiple sensitive actions. Please request "
                        "and confirm them one at a time."
                    )
                call = sensitive_calls[0]
                name = str(call.name or "")
                self._pending[session_id] = PendingConfirmation(
                    expires_at=time.monotonic() + self.confirmation_ttl_seconds,
                    tool_name=name,
                    arguments=dict(call.args or {}),
                    contents=list(contents),
                    model_content=model_content,
                )
                return (
                    f"Please confirm before I run the sensitive Hubitat action "
                    f"`{name}`. Reply “confirm” to proceed."
                )
            result_parts: list[types.Part] = []
            for call in calls:
                name = str(call.name or "")
                arguments = dict(call.args or {})
                declared = tool_by_name.get(name)
                if declared is None:
                    payload = {"error": f"Model requested undeclared MCP tool: {name}"}
                else:
                    try:
                        result = await self.mcp.call_tool(name, arguments)
                        payload = self._result_payload(result)
                    except Exception as exc:
                        logger.exception("MCP tool %s failed", name)
                        payload = {"error": str(exc)}
                result_parts.append(types.Part.from_function_response(
                    name=name, response=payload
                ))
            contents.extend([
                model_content,
                types.Content(role="tool", parts=result_parts),
            ])
        raise RuntimeError("The agent exceeded its MCP tool-round limit")


__all__ = ["UnifiedMCPAgent"]
