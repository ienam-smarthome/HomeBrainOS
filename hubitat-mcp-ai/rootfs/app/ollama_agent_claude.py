from __future__ import annotations

import json
import re
import time
from typing import Any

from kingpanther_skill import KINGPANTHER_SYSTEM_PROMPT
from mcp_client import HubitatMCPClient, MCPTool, MCPToolResult
from ollama_agent_fast import OllamaUnavailable
from ollama_agent_inference import OllamaMCPAgent as InferenceOllamaMCPAgent


class ClaudeStyleOllamaAgent(InferenceOllamaMCPAgent):
    """Ollama-first MCP agent with compact planning and natural final synthesis.

    The previous agent sent a large fixed tool set to the 9B response model and
    gated real questions behind a synthetic readiness probe. This class instead:

    * allows real questions whenever the Ollama server and model are available;
    * optionally uses a smaller installed model for tool planning;
    * exposes only a compact, query-relevant MCP tool set to the planner;
    * executes MCP tools sequentially; and
    * asks the response model for a grounded, Claude-style final answer without
      resending all tool schemas.
    """

    def __init__(
        self,
        client: HubitatMCPClient,
        base_url: str,
        model: str,
        *,
        planner_model: str = "",
        planner_timeout_seconds: float = 45,
        response_timeout_seconds: float = 90,
        planner_tool_limit: int = 6,
        tool_result_limit_chars: int = 12000,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            client=client,
            base_url=base_url,
            model=model,
            **kwargs,
        )
        self.configured_planner_model = str(planner_model or "").strip()
        self.planner_timeout_seconds = max(10.0, float(planner_timeout_seconds))
        self.response_timeout_seconds = max(15.0, float(response_timeout_seconds))
        self.planner_tool_limit = max(3, int(planner_tool_limit))
        self.tool_result_limit_chars = max(2000, int(tool_result_limit_chars))
        self._last_agent_status: dict[str, Any] = {
            "state": "idle",
            "planner_model": self.configured_planner_model or self.model,
            "response_model": self.model,
        }

    async def runtime_status(self, force: bool = False) -> dict[str, Any]:
        server = await self.health(force=force)
        planner = self._resolve_planner_model(server.get("models") or [])
        loaded_names: list[str] = []
        running_error: str | None = None
        if server.get("online"):
            try:
                response = await self._http.get(
                    f"{self.base_url}/api/ps",
                    timeout=self.health_timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                loaded_names = [
                    str(item.get("name") or item.get("model") or "")
                    for item in payload.get("models", [])
                    if isinstance(item, dict)
                ]
            except Exception as exc:
                running_error = str(exc)

        return {
            "online": bool(server.get("online")),
            "model": self.model,
            "model_present": bool(server.get("model_present")),
            "model_loaded": self._model_matches(self.model, loaded_names),
            "planner_model": planner,
            "planner_present": self._model_matches(planner, server.get("models") or []),
            "planner_loaded": self._model_matches(planner, loaded_names),
            "installed_models": list(server.get("models") or []),
            "loaded_models": loaded_names,
            "error": server.get("error"),
            "running_models_error": running_error,
            "last_agent": dict(self._last_agent_status),
        }

    async def answer(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        health = await self.health()
        if not health.get("online"):
            raise OllamaUnavailable(health.get("error") or "Ollama is offline")
        if health.get("model_present") is False:
            raise OllamaUnavailable(
                f"Configured Ollama model {self.model} is not installed."
            )

        installed_models = list(health.get("models") or [])
        planner_model = self._resolve_planner_model(installed_models)
        tools = await self.client.list_tools()
        selected = self._select_compact_tools(query, tools)
        ollama_tools = [tool.as_ollama_tool() for tool in selected]

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": self._planner_prompt(),
            }
        ]
        for item in (history or [])[-8:]:
            role = item.get("role")
            content = item.get("content")
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": str(content)})
        messages.append({"role": "user", "content": query})

        tools_used: list[dict[str, Any]] = []
        planning_content = ""
        self._last_agent_status = {
            "state": "planning",
            "planner_model": planner_model,
            "response_model": self.model,
            "query": query[:200],
            "started_at": time.time(),
        }

        try:
            for round_number in range(1, self.max_tool_rounds + 1):
                body = await self._chat(
                    model=planner_model,
                    messages=messages,
                    tools=ollama_tools,
                    timeout_seconds=self.planner_timeout_seconds,
                    num_ctx=min(self.num_ctx, 4096),
                    num_predict=min(self.num_predict, 160),
                    temperature=0.1,
                )
                message = body.get("message") or {}
                planning_content = str(message.get("content") or "").strip()
                tool_calls = message.get("tool_calls") or []

                if not tool_calls:
                    break

                messages.append(
                    {
                        "role": "assistant",
                        "content": planning_content,
                        "tool_calls": tool_calls,
                    }
                )

                for tool_call in tool_calls:
                    name, arguments = self._parse_tool_call(tool_call)
                    if not name:
                        tool_text = "The model requested an unnamed tool."
                        record = {
                            "name": "",
                            "arguments": arguments,
                            "success": False,
                            "error": tool_text,
                        }
                    elif self._sensitive_confirmation_required(name, arguments, query):
                        tool_text = (
                            "This operation requires explicit confirmation in the user's "
                            "latest message. Explain what would be changed and ask for confirmation."
                        )
                        record = {
                            "name": name,
                            "arguments": arguments,
                            "success": False,
                            "blocked": "confirmation-required",
                        }
                    else:
                        try:
                            result = await self.client.call_tool(name, arguments)
                            tool_text = self._compact_tool_result(result)
                            record = {
                                "name": name,
                                "arguments": arguments,
                                "success": not result.is_error,
                                "preview": tool_text[:700],
                            }
                        except Exception as exc:
                            tool_text = f"MCP tool error: {exc}"
                            record = {
                                "name": name,
                                "arguments": arguments,
                                "success": False,
                                "error": str(exc),
                            }
                    tools_used.append(record)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_name": name or "unknown_tool",
                            "content": tool_text,
                        }
                    )

                # After a successful data-bearing tool call, give the planner one
                # more chance to request missing detail. Most requests finish in
                # a single tool round, avoiding the old large multi-round loop.
                if round_number >= self.max_tool_rounds:
                    break

            if not tools_used and planning_content:
                content = planning_content
                route = "ollama"
            else:
                self._last_agent_status["state"] = "synthesising"
                synthesis_messages = self._synthesis_messages(
                    query=query,
                    history=history or [],
                    planner_messages=messages,
                    planner_content=planning_content,
                )
                body = await self._chat(
                    model=self.model,
                    messages=synthesis_messages,
                    tools=None,
                    timeout_seconds=self.response_timeout_seconds,
                    num_ctx=self.num_ctx,
                    num_predict=self.num_predict,
                    temperature=0.25,
                )
                content = str((body.get("message") or {}).get("content") or "").strip()
                route = "ollama+mcp"

            if not content:
                raise OllamaUnavailable("Ollama returned an empty final answer")

            elapsed = round((time.perf_counter() - started) * 1000)
            self.record_inference_success(elapsed, source="agent")
            self._last_agent_status = {
                "state": "ready",
                "planner_model": planner_model,
                "response_model": self.model,
                "tools_used": [item.get("name") for item in tools_used],
                "elapsed_ms": elapsed,
                "completed_at": time.time(),
            }
            return {
                "success": True,
                "route": route,
                "intent": "ollama-claude-agent",
                "message": content,
                "model": self.model,
                "planner_model": planner_model,
                "tools_used": tools_used,
                "tool_rounds": len(
                    [item for item in messages if item.get("role") == "assistant" and item.get("tool_calls")]
                ),
                "selected_tools": [tool.name for tool in selected],
                "elapsed_ms": elapsed,
            }
        except Exception as exc:
            elapsed = round((time.perf_counter() - started) * 1000)
            self._last_agent_status = {
                "state": "error",
                "planner_model": planner_model,
                "response_model": self.model,
                "error": str(exc),
                "elapsed_ms": elapsed,
                "completed_at": time.time(),
            }
            state = "timeout" if "timed out" in str(exc).lower() else "error"
            self.record_inference_failure(
                str(exc),
                state=state,
                elapsed_ms=elapsed,
                source="agent",
            )
            if isinstance(exc, OllamaUnavailable):
                raise
            raise OllamaUnavailable(str(exc)) from exc

    async def _chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        timeout_seconds: float,
        num_ctx: int,
        num_predict: int,
        temperature: float,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": False,
            "keep_alive": self.keep_alive,
            "options": {
                "num_ctx": num_ctx,
                "num_predict": num_predict,
                "temperature": temperature,
            },
        }
        if tools:
            payload["tools"] = tools
        try:
            response = await self._http.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict):
                raise RuntimeError("Ollama returned a non-object response")
            return body
        except Exception as exc:
            text = str(exc) or exc.__class__.__name__
            if "timeout" in text.lower() or "timed out" in text.lower():
                raise OllamaUnavailable(
                    f"Ollama model {model} timed out after {timeout_seconds:g} seconds"
                ) from exc
            raise OllamaUnavailable(f"Ollama model {model} failed: {text}") from exc

    def _resolve_planner_model(self, installed_models: list[str]) -> str:
        if self.configured_planner_model:
            if self._model_matches(self.configured_planner_model, installed_models):
                return self.configured_planner_model
            # Do not break the assistant because an optional planner was removed.
            return self.model

        candidates = [
            name
            for name in installed_models
            if name and not any(term in name.lower() for term in ("embed", "nomic", "bge"))
        ]
        if not candidates:
            return self.model

        def size_key(name: str) -> tuple[float, int, str]:
            match = re.search(r"(?<!\d)(\d+(?:\.\d+)?)b(?:\b|$)", name.lower())
            size = float(match.group(1)) if match else 999.0
            same_family = 0 if name.split(":")[0] == self.model.split(":")[0] else 1
            return size, same_family, name

        candidates.sort(key=size_key)
        return candidates[0]

    def _select_compact_tools(
        self,
        query: str,
        tools: list[MCPTool],
    ) -> list[MCPTool]:
        q = query.lower()
        query_tokens = self._tokens(query)
        preferred: set[str] = {"hub_search_tools"}

        if any(term in q for term in ("device", "light", "switch", "sensor", "thermostat", "battery")):
            preferred.update({"hub_list_devices", "hub_get_device"})
        if any(term in q for term in ("turn ", "switch ", "set ", "lock", "unlock")):
            preferred.add("hub_call_device_command")
        if any(term in q for term in ("hub", "memory", "firmware", "update", "health", "cpu")):
            preferred.add("hub_get_info")
        if any(term in q for term in ("rule", "automation", "schedule", "trigger")):
            preferred.update({"hub_get_tool_guide", "hub_search_tools"})
        if any(term in q for term in ("room", "rooms")):
            preferred.add("hub_read_rooms")

        scored: list[tuple[float, MCPTool]] = []
        for tool in tools:
            text = f"{tool.name} {tool.description}".lower()
            overlap = len(query_tokens & self._tokens(text))
            score = overlap * 5.0
            if tool.name in preferred:
                score += 100.0
            if tool.name.startswith("hub_read_") and any(token in text for token in query_tokens):
                score += 5.0
            if tool.name.startswith("hub_manage_") and not re.search(
                r"\b(create|change|modify|delete|remove|set|turn|switch|update|enable|disable)\b",
                q,
            ):
                score -= 8.0
            scored.append((score, tool))

        scored.sort(key=lambda item: (-item[0], item[1].name))
        selected: list[MCPTool] = []
        seen: set[str] = set()
        for score, tool in scored:
            if tool.name in seen:
                continue
            if score <= 0 and len(selected) >= 3:
                continue
            selected.append(tool)
            seen.add(tool.name)
            if len(selected) >= self.planner_tool_limit:
                break
        return selected

    @staticmethod
    def _parse_tool_call(tool_call: Any) -> tuple[str, dict[str, Any]]:
        function = tool_call.get("function") if isinstance(tool_call, dict) else None
        function = function if isinstance(function, dict) else {}
        name = str(function.get("name") or "").strip()
        arguments = function.get("arguments") or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except Exception:
                arguments = {}
        if not isinstance(arguments, dict):
            arguments = {}
        return name, arguments

    def _compact_tool_result(self, result: MCPToolResult) -> str:
        if result.data is not None and not isinstance(result.data, str):
            text = json.dumps(result.data, ensure_ascii=False, separators=(",", ":"), default=str)
        elif result.text:
            text = result.text
        elif result.data is not None:
            text = str(result.data)
        else:
            text = json.dumps(result.raw, ensure_ascii=False, separators=(",", ":"), default=str)

        if len(text) <= self.tool_result_limit_chars:
            return text
        head = int(self.tool_result_limit_chars * 0.75)
        tail = self.tool_result_limit_chars - head
        return (
            text[:head]
            + "\n...[tool result compacted for the local model]...\n"
            + text[-tail:]
        )

    def _planner_prompt(self) -> str:
        return (
            KINGPANTHER_SYSTEM_PROMPT
            + "\n\nYou are the planning stage of a natural smart-home assistant. "
            "For any question about the user's live home, always call the minimum MCP tool or "
            "gateway needed before answering. Use hub_search_tools when the required tool is not "
            "obvious. A gateway may be called with no arguments to discover its sub-tools, then "
            "called again with tool and args. Do not produce a final live-state answer from memory. "
            "Keep planning terse and prefer one focused tool call at a time because the hub is "
            "resource constrained."
        )

    def _synthesis_messages(
        self,
        *,
        query: str,
        history: list[dict[str, str]],
        planner_messages: list[dict[str, Any]],
        planner_content: str,
    ) -> list[dict[str, Any]]:
        tool_context: list[dict[str, str]] = []
        for item in planner_messages:
            if item.get("role") == "tool":
                tool_context.append(
                    {
                        "role": "user",
                        "content": (
                            f"MCP result from {item.get('tool_name', 'tool')}:\n"
                            f"{item.get('content', '')}"
                        ),
                    }
                )

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    KINGPANTHER_SYSTEM_PROMPT
                    + "\n\nYou are now the final response stage. Answer in a natural, confident, "
                    "Claude-style conversational tone. Ground every live fact in the MCP results "
                    "provided below. Do not mention internal planning, schemas, JSON, fast paths, "
                    "or tool mechanics unless the user explicitly asks. Be concise but include the "
                    "important names, values, warnings, and whether an action was confirmed. If the "
                    "MCP data is incomplete, say exactly what is missing rather than guessing."
                ),
            }
        ]
        for item in history[-6:]:
            if item.get("role") in {"user", "assistant"} and item.get("content"):
                messages.append(
                    {"role": item["role"], "content": str(item["content"])}
                )
        messages.append({"role": "user", "content": query})
        messages.extend(tool_context)
        if planner_content:
            messages.append(
                {
                    "role": "user",
                    "content": f"Planner note (not authoritative): {planner_content}",
                }
            )
        messages.append(
            {
                "role": "user",
                "content": "Give the final answer to the original question now.",
            }
        )
        return messages

    @staticmethod
    def _model_matches(model: str, names: list[str]) -> bool:
        if not model:
            return False
        return model in names or any(
            name.split(":")[0] == model.split(":")[0] for name in names
        )


__all__ = ["ClaudeStyleOllamaAgent", "OllamaUnavailable"]
