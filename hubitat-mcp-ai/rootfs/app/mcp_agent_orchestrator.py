from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import quote

import httpx

from mcp_client import HubitatMCPClient, MCPTool, MCPToolResult

logger = logging.getLogger("HomeBrainOS.Orchestrator")


class UnifiedMCPAgent:
    """Native Gemini function-calling agent backed by live Hubitat MCP schemas."""

    def __init__(
        self,
        mcp_client: HubitatMCPClient,
        gemini_api_key: str,
        model_name: str = "gemini-3.6-flash",
        *,
        gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout_seconds: float = 15,
        tool_limit: int = 48,
        max_tool_rounds: int = 6,
        require_sensitive_confirmation: bool = True,
    ) -> None:
        self.mcp = mcp_client
        self.api_key = str(gemini_api_key or "").strip()
        self.model_name = str(model_name or "").strip()
        self.base_url = str(gemini_base_url or "").rstrip("/")
        self.tool_limit = max(1, int(tool_limit))
        self.max_tool_rounds = max(1, int(max_tool_rounds))
        self.require_sensitive_confirmation = bool(require_sensitive_confirmation)
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(max(3.0, float(timeout_seconds))))

    async def close(self) -> None:
        await self._http.aclose()

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
        confirmation = (
            "Before any sensitive, destructive, security, hub-management, or automation-rule "
            "write, ask for explicit confirmation and do not call the write tool in that turn."
            if self.require_sensitive_confirmation
            else ""
        )
        return (
            "You are HomeBrainOS, a concise smart-home assistant. Use the supplied Hubitat MCP "
            "functions for every live state claim and action. Match informal names against the "
            "live manifest, using exact IDs when a tool supports them. Never invent devices, "
            "states, tool results, or successful actions. If a target is genuinely ambiguous, "
            "ask one short clarifying question. "
            f"{confirmation}\n\nLIVE DEVICE MANIFEST\n{manifest}"
        )

    @staticmethod
    def _tool_declaration(tool: MCPTool) -> dict[str, Any]:
        schema = tool.input_schema if isinstance(tool.input_schema, dict) else {}
        return {
            "name": tool.name,
            "description": tool.description or tool.name,
            "parameters": schema or {"type": "object", "properties": {}},
        }

    @staticmethod
    def _normalise_history(history: Any) -> list[dict[str, Any]]:
        contents: list[dict[str, Any]] = []
        for item in list(history or [])[-20:]:
            if hasattr(item, "model_dump"):
                item = item.model_dump()
            if not isinstance(item, dict):
                continue
            role = "model" if item.get("role") in {"assistant", "model"} else "user"
            text = item.get("content") or item.get("text")
            if text:
                contents.append({"role": role, "parts": [{"text": str(text)}]})
        return contents

    async def _generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("Gemini API key is not configured")
        if not self.model_name:
            raise RuntimeError("Gemini model is not configured")
        url = (
            f"{self.base_url}/models/{quote(self.model_name, safe='')}:generateContent"
            f"?key={quote(self.api_key, safe='')}"
        )
        response = await self._http.post(url, json=payload)
        if response.status_code >= 400:
            detail = response.text.strip()
            raise RuntimeError(f"Gemini HTTP {response.status_code}: {detail[:500]}")
        value = response.json()
        if not isinstance(value, dict):
            raise RuntimeError("Gemini returned an invalid response")
        return value

    @staticmethod
    def _content(response: dict[str, Any]) -> dict[str, Any]:
        candidates = response.get("candidates") or []
        if not candidates or not isinstance(candidates[0], dict):
            feedback = response.get("promptFeedback") or {}
            raise RuntimeError(f"Gemini returned no candidate: {feedback}")
        content = candidates[0].get("content") or {}
        if not isinstance(content, dict):
            raise RuntimeError("Gemini candidate contained no content")
        return content

    @staticmethod
    def _text(content: dict[str, Any]) -> str:
        return "\n".join(
            str(part.get("text"))
            for part in content.get("parts") or []
            if isinstance(part, dict) and part.get("text")
        ).strip()

    @staticmethod
    def _result_payload(result: MCPToolResult) -> dict[str, Any]:
        if result.is_error:
            return {"error": result.text or "MCP tool failed"}
        value = result.data if result.data is not None else result.text
        return {"result": value}

    async def process_user_request(
        self,
        user_prompt: str,
        conversation_history: Any = None,
    ) -> str:
        tools = (await self.mcp.list_tools())[: self.tool_limit]
        contents = self._normalise_history(conversation_history)
        contents.append({"role": "user", "parts": [{"text": str(user_prompt).strip()}]})
        payload: dict[str, Any] = {
            "systemInstruction": {
                "parts": [{"text": await self._build_system_instruction()}]
            },
            "contents": contents,
            "generationConfig": {"temperature": 0.1},
        }
        if tools:
            payload["tools"] = [
                {"functionDeclarations": [self._tool_declaration(tool) for tool in tools]}
            ]

        for _ in range(self.max_tool_rounds):
            content = self._content(await self._generate(payload))
            calls = [
                part["functionCall"]
                for part in content.get("parts") or []
                if isinstance(part, dict) and isinstance(part.get("functionCall"), dict)
            ]
            if not calls:
                return self._text(content) or "Done."

            payload["contents"].append(content)
            result_parts: list[dict[str, Any]] = []
            for call in calls:
                name = str(call.get("name") or "")
                arguments = call.get("args") if isinstance(call.get("args"), dict) else {}
                logger.info("Executing MCP tool %s", name)
                try:
                    result = await self.mcp.call_tool(name, arguments)
                    response_value = self._result_payload(result)
                except Exception as exc:
                    logger.exception("MCP tool %s failed", name)
                    response_value = {"error": str(exc)}
                result_parts.append(
                    {
                        "functionResponse": {
                            "name": name,
                            "response": response_value,
                        }
                    }
                )
            payload["contents"].append({"role": "user", "parts": result_parts})

        raise RuntimeError("The agent exceeded its MCP tool-round limit")


__all__ = ["UnifiedMCPAgent"]
