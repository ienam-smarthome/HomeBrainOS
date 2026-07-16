from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx

from kingpanther_skill import KINGPANTHER_SYSTEM_PROMPT
from mcp_client import HubitatMCPClient, MCPTool, MCPToolResult


class OllamaUnavailable(RuntimeError):
    pass


class OllamaMCPAgent:
    def __init__(
        self,
        client: HubitatMCPClient,
        base_url: str,
        model: str,
        timeout_seconds: float = 75,
        health_timeout_seconds: float = 3,
        num_ctx: int = 8192,
        num_predict: int = 220,
        keep_alive: str = "15m",
        tool_limit: int = 16,
        max_tool_rounds: int = 6,
        require_sensitive_confirmation: bool = True,
    ) -> None:
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.model = model.strip()
        self.timeout_seconds = max(5.0, float(timeout_seconds))
        self.health_timeout_seconds = max(1.0, float(health_timeout_seconds))
        self.num_ctx = max(2048, int(num_ctx))
        self.num_predict = max(40, int(num_predict))
        self.keep_alive = keep_alive
        self.tool_limit = max(6, int(tool_limit))
        self.max_tool_rounds = max(1, int(max_tool_rounds))
        self.require_sensitive_confirmation = bool(require_sensitive_confirmation)
        self._http = httpx.AsyncClient(follow_redirects=True)
        self._health_cache: tuple[float, dict[str, Any]] | None = None

    async def close(self) -> None:
        await self._http.aclose()

    async def health(self, force: bool = False) -> dict[str, Any]:
        now = time.time()
        if not force and self._health_cache and now - self._health_cache[0] < 15:
            return dict(self._health_cache[1])
        if not self.base_url or not self.model:
            result = {"online": False, "error": "Ollama is not configured"}
            self._health_cache = (now, result)
            return result
        try:
            response = await self._http.get(
                f"{self.base_url}/api/tags",
                timeout=self.health_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            names = [
                str(item.get("name") or item.get("model") or "")
                for item in payload.get("models", [])
                if isinstance(item, dict)
            ]
            model_present = self.model in names or any(
                name.split(":")[0] == self.model.split(":")[0] for name in names
            )
            result = {
                "online": True,
                "model": self.model,
                "model_present": model_present,
                "models": names[:20],
            }
        except Exception as exc:
            result = {"online": False, "error": str(exc), "model": self.model}
        self._health_cache = (now, result)
        return dict(result)

    async def answer(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        health = await self.health()
        if not health.get("online"):
            raise OllamaUnavailable(health.get("error") or "Ollama is offline")

        tools = await self.client.list_tools()
        selected = self._select_tools(query, tools)
        ollama_tools = [tool.as_ollama_tool() for tool in selected]

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": KINGPANTHER_SYSTEM_PROMPT},
        ]
        for item in (history or [])[-10:]:
            role = item.get("role")
            content = item.get("content")
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": str(content)})
        messages.append({"role": "user", "content": query})

        tools_used: list[dict[str, Any]] = []

        for _round in range(self.max_tool_rounds):
            payload: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "keep_alive": self.keep_alive,
                "options": {
                    "num_ctx": self.num_ctx,
                    "num_predict": self.num_predict,
                    "temperature": 0.25,
                },
            }
            if ollama_tools:
                payload["tools"] = ollama_tools

            try:
                response = await self._http.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                body = response.json()
            except Exception as exc:
                self._health_cache = None
                raise OllamaUnavailable(str(exc)) from exc

            message = body.get("message") or {}
            content = str(message.get("content") or "").strip()
            tool_calls = message.get("tool_calls") or []

            if not tool_calls:
                if content:
                    return {
                        "success": True,
                        "route": "ollama+mcp",
                        "intent": "ollama-agent",
                        "message": content,
                        "model": self.model,
                        "tools_used": tools_used,
                    }
                raise OllamaUnavailable("Ollama returned no answer or tool call")

            messages.append(
                {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls,
                }
            )

            for tool_call in tool_calls:
                function = (
                    tool_call.get("function")
                    if isinstance(tool_call, dict)
                    else None
                ) or {}
                name = str(function.get("name") or "").strip()
                arguments = function.get("arguments") or {}
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except Exception:
                        arguments = {}
                if not isinstance(arguments, dict):
                    arguments = {}

                if not name:
                    tool_text = "The model requested an unnamed tool."
                    result_record = {
                        "name": "",
                        "arguments": arguments,
                        "success": False,
                        "error": tool_text,
                    }
                elif self._sensitive_confirmation_required(name, arguments, query):
                    tool_text = (
                        "This is a sensitive Hubitat operation. Ask the user for explicit "
                        "confirmation, naming the exact operation and device, before calling it."
                    )
                    result_record = {
                        "name": name,
                        "arguments": arguments,
                        "success": False,
                        "blocked": "confirmation-required",
                    }
                else:
                    try:
                        result = await self.client.call_tool(name, arguments)
                        tool_text = self._tool_result_text(result)
                        result_record = {
                            "name": name,
                            "arguments": arguments,
                            "success": not result.is_error,
                            "preview": tool_text[:500],
                        }
                    except Exception as exc:
                        tool_text = f"MCP tool error: {exc}"
                        result_record = {
                            "name": name,
                            "arguments": arguments,
                            "success": False,
                            "error": str(exc),
                        }

                tools_used.append(result_record)
                messages.append(
                    {
                        "role": "tool",
                        "content": tool_text,
                    }
                )

        return {
            "success": False,
            "route": "ollama+mcp",
            "intent": "tool-round-limit",
            "message": "The request used too many MCP tool steps and was stopped safely.",
            "model": self.model,
            "tools_used": tools_used,
        }

    def _select_tools(self, query: str, tools: list[MCPTool]) -> list[MCPTool]:
        query_tokens = self._tokens(query)
        must_include = {
            "hub_search_tools",
            "hub_get_tool_guide",
            "hub_list_devices",
            "hub_get_device",
            "hub_call_device_command",
            "hub_get_info",
        }

        scored: list[tuple[float, MCPTool]] = []
        for tool in tools:
            text = f"{tool.name} {tool.description}".lower()
            tool_tokens = self._tokens(text)
            overlap = len(query_tokens & tool_tokens)
            score = overlap * 5.0
            for token in query_tokens:
                if token and token in tool.name.lower():
                    score += 4.0
                elif token and token in text:
                    score += 1.0
            if tool.name in must_include:
                score += 100.0
            if tool.name.startswith("hub_read_"):
                score += 0.5
            scored.append((score, tool))

        scored.sort(key=lambda pair: (-pair[0], pair[1].name))
        selected: list[MCPTool] = []
        seen = set()
        for score, tool in scored:
            if tool.name in seen:
                continue
            if score <= 0 and len(selected) >= len(must_include):
                continue
            selected.append(tool)
            seen.add(tool.name)
            if len(selected) >= self.tool_limit:
                break
        return selected

    @staticmethod
    def _tokens(value: str) -> set[str]:
        stop = {
            "the", "a", "an", "is", "are", "to", "of", "in", "on", "off",
            "my", "me", "please", "what", "which", "and", "for", "with",
        }
        return {
            token
            for token in re.findall(r"[a-z0-9_]+", value.lower())
            if len(token) > 1 and token not in stop
        }

    def _sensitive_confirmation_required(
        self,
        name: str,
        arguments: dict[str, Any],
        latest_query: str,
    ) -> bool:
        if not self.require_sensitive_confirmation:
            return False
        latest = latest_query.lower()
        confirmed = any(
            phrase in latest
            for phrase in (
                "confirm", "i confirm", "yes, do it", "yes do it",
                "proceed with", "approved",
            )
        )
        if confirmed:
            return False

        combined = f"{name} {json.dumps(arguments, ensure_ascii=False)}".lower()
        sensitive_terms = (
            "unlock", "open garage", "disarm", "delete", "remove",
            "reboot", "shutdown", "wipe", "reset radio", "factory",
            "firmware", "update_firmware", "code", "driver", "app source",
            "restore backup", "disable cloud", "network disconnect",
            "hsm", "security",
        )
        return any(term in combined for term in sensitive_terms)

    @staticmethod
    def _tool_result_text(result: MCPToolResult) -> str:
        if result.text:
            return result.text
        if result.data is not None:
            return json.dumps(result.data, ensure_ascii=False)
        return json.dumps(result.raw, ensure_ascii=False)
