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
    """Ollama-first MCP agent with robust tool execution and natural synthesis.

    Local models do not always emit Ollama's native ``tool_calls`` structure. Some
    return the intended call as JSON in the assistant content instead. This agent
    accepts both forms, never exposes a raw plan to the user, and uses generic MCP
    discovery when a live-home question reaches the planner without a tool call.
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
        requires_live_data = self._requires_live_data(query)

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._planner_prompt()}
        ]
        for item in (history or [])[-8:]:
            role = item.get("role")
            content = item.get("content")
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": str(content)})
        messages.append({"role": "user", "content": query})

        tools_used: list[dict[str, Any]] = []
        planning_content = ""
        discovery_injected = False
        successful_data_call = False
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
                tool_calls = list(message.get("tool_calls") or [])

                # Qwen and some other local models occasionally print a valid tool
                # request as JSON instead of filling Ollama's tool_calls property.
                if not tool_calls and planning_content:
                    tool_calls = self._extract_text_tool_calls(planning_content)

                if not tool_calls:
                    if requires_live_data and not successful_data_call:
                        if not discovery_injected and self._tool_available(
                            "hub_search_tools", tools
                        ):
                            discovery_injected = True
                            record, tool_text = await self._execute_tool_call(
                                "hub_search_tools",
                                {"query": query},
                                query,
                            )
                            tools_used.append(record)
                            messages.append(
                                {
                                    "role": "assistant",
                                    "content": (
                                        "I need MCP discovery before answering this live-home question."
                                    ),
                                }
                            )
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_name": "hub_search_tools",
                                    "content": tool_text,
                                }
                            )
                            continue
                        raise OllamaUnavailable(
                            "The planner did not execute an MCP tool for a live-home question."
                        )
                    break

                normalised_calls: list[dict[str, Any]] = []
                for tool_call in tool_calls:
                    name, arguments = self._parse_tool_call(tool_call)
                    if name:
                        normalised_calls.append(
                            {
                                "function": {
                                    "name": name,
                                    "arguments": arguments,
                                }
                            }
                        )

                if not normalised_calls:
                    if requires_live_data and not successful_data_call:
                        raise OllamaUnavailable(
                            "The planner produced a tool request that could not be parsed."
                        )
                    break

                messages.append(
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": normalised_calls,
                    }
                )

                round_had_discovery = False
                round_had_successful_data = False
                for tool_call in normalised_calls:
                    name, arguments = self._parse_tool_call(tool_call)
                    record, tool_text = await self._execute_tool_call(
                        name,
                        arguments,
                        query,
                    )
                    tools_used.append(record)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_name": name or "unknown_tool",
                            "content": tool_text,
                        }
                    )
                    if self._is_discovery_call(name, arguments):
                        round_had_discovery = True
                    elif record.get("success"):
                        round_had_successful_data = True
                        successful_data_call = True

                # Once authoritative data has been returned, go directly to final
                # synthesis. The previous extra planner round roughly doubled the
                # response time on a CPU-hosted 9B model.
                if round_had_successful_data and not round_had_discovery:
                    break
                if round_number >= self.max_tool_rounds:
                    break

            if requires_live_data and not successful_data_call:
                raise OllamaUnavailable(
                    "The MCP planning stage finished without authoritative home data."
                )

            if not tools_used:
                if not planning_content or self._looks_like_tool_json(planning_content):
                    raise OllamaUnavailable("Ollama returned no usable answer")
                content = planning_content
                route = "ollama"
            else:
                self._last_agent_status["state"] = "synthesising"
                synthesis_messages = self._synthesis_messages(
                    query=query,
                    history=history or [],
                    planner_messages=messages,
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
            if self._looks_like_tool_json(content):
                raise OllamaUnavailable(
                    "Ollama returned an internal tool plan instead of a final answer."
                )

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
                    [
                        item
                        for item in messages
                        if item.get("role") == "assistant"
                        and item.get("tool_calls")
                    ]
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

    async def _execute_tool_call(
        self,
        name: str,
        arguments: dict[str, Any],
        query: str,
    ) -> tuple[dict[str, Any], str]:
        if not name:
            text = "The model requested an unnamed tool."
            return {
                "name": "",
                "arguments": arguments,
                "success": False,
                "error": text,
            }, text

        placeholder = self._find_placeholder(arguments)
        if placeholder:
            text = (
                f"Invalid placeholder {placeholder!r}. Use a concrete value or discover the "
                "correct MCP schema before retrying."
            )
            return {
                "name": name,
                "arguments": arguments,
                "success": False,
                "error": text,
            }, text

        if self._sensitive_confirmation_required(name, arguments, query):
            text = (
                "This operation requires explicit confirmation in the user's latest "
                "message. Explain what would be changed and ask for confirmation."
            )
            return {
                "name": name,
                "arguments": arguments,
                "success": False,
                "blocked": "confirmation-required",
            }, text

        try:
            result = await self.client.call_tool(name, arguments)
            tool_text = self._compact_tool_result(result)
            return {
                "name": name,
                "arguments": arguments,
                "success": not result.is_error,
                "preview": tool_text[:700],
            }, tool_text
        except Exception as exc:
            tool_text = f"MCP tool error: {exc}"
            return {
                "name": name,
                "arguments": arguments,
                "success": False,
                "error": str(exc),
            }, tool_text

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
            return self.model

        candidates = [
            name
            for name in installed_models
            if name
            and not any(term in name.lower() for term in ("embed", "nomic", "bge"))
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

        if any(term in q for term in ("what's happening", "what is happening", "home status", "at home")):
            preferred.update(
                {
                    "hub_list_devices",
                    "hub_get_info",
                    "hub_read_rooms",
                    "hub_read_diagnostics",
                }
            )
        if any(
            term in q
            for term in (
                "attention",
                "offline",
                "stale",
                "not responding",
                "unresponsive",
                "low battery",
                "low batteries",
            )
        ):
            preferred.update(
                {
                    "hub_read_diagnostics",
                    "hub_list_devices",
                    "hub_get_info",
                }
            )
        if any(
            term in q
            for term in (
                "device",
                "light",
                "switch",
                "sensor",
                "thermostat",
                "battery",
                "weather",
                "rain",
                "temperature",
                "presence",
                "motion",
            )
        ):
            preferred.update({"hub_list_devices", "hub_get_device"})
        if any(term in q for term in ("turn ", "switch ", "set ", "lock", "unlock")):
            preferred.add("hub_call_device_command")
        if any(term in q for term in ("hub", "memory", "firmware", "update", "health", "cpu")):
            preferred.add("hub_get_info")
        if any(term in q for term in ("rule", "automation", "schedule", "trigger")):
            preferred.update(
                {"hub_get_tool_guide", "hub_search_tools", "hub_read_rules"}
            )
        if any(term in q for term in ("room", "rooms")):
            preferred.add("hub_read_rooms")

        scored: list[tuple[float, MCPTool]] = []
        for tool in tools:
            text = f"{tool.name} {tool.description}".lower()
            overlap = len(query_tokens & self._tokens(text))
            score = overlap * 5.0
            if tool.name in preferred:
                score += 100.0
            if tool.name.startswith("hub_read_") and any(
                token in text for token in query_tokens
            ):
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

    @classmethod
    def _extract_text_tool_calls(cls, content: str) -> list[dict[str, Any]]:
        values = cls._json_values(content)
        calls: list[dict[str, Any]] = []
        for value in values:
            candidates: list[Any]
            if isinstance(value, list):
                candidates = value
            elif isinstance(value, dict) and isinstance(value.get("tool_calls"), list):
                candidates = value["tool_calls"]
            else:
                candidates = [value]
            for candidate in candidates:
                name, arguments = cls._parse_tool_call(candidate)
                if name:
                    calls.append(
                        {
                            "function": {
                                "name": name,
                                "arguments": arguments,
                            }
                        }
                    )
        return calls

    @staticmethod
    def _json_values(content: str) -> list[Any]:
        text = str(content or "").strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        decoder = json.JSONDecoder()
        values: list[Any] = []
        index = 0
        while index < len(text):
            start_candidates = [
                position
                for position in (text.find("{", index), text.find("[", index))
                if position >= 0
            ]
            if not start_candidates:
                break
            start = min(start_candidates)
            try:
                value, end = decoder.raw_decode(text[start:])
                values.append(value)
                index = start + end
            except json.JSONDecodeError:
                index = start + 1
        return values

    @staticmethod
    def _parse_tool_call(tool_call: Any) -> tuple[str, dict[str, Any]]:
        if not isinstance(tool_call, dict):
            return "", {}

        function = tool_call.get("function")
        function = function if isinstance(function, dict) else {}
        name = str(
            function.get("name")
            or tool_call.get("name")
            or tool_call.get("tool")
            or ""
        ).strip()
        arguments: Any = (
            function.get("arguments")
            if "arguments" in function
            else tool_call.get("arguments")
            if "arguments" in tool_call
            else tool_call.get("parameters")
            if "parameters" in tool_call
            else tool_call.get("input")
            if "input" in tool_call
            else tool_call.get("args")
        )
        arguments = arguments or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except Exception:
                arguments = {}
        if not isinstance(arguments, dict):
            arguments = {}

        # Some models wrap a direct call as:
        # {"name":"hub_list_devices","parameters":{"tool":"hub_list_devices","args":{...}}}
        # Unwrap this without disturbing genuine gateway calls.
        nested_tool = str(arguments.get("tool") or "").strip()
        nested_args = arguments.get("args")
        if (
            nested_tool
            and nested_tool == name
            and isinstance(nested_args, dict)
            and not name.startswith(("hub_read_", "hub_manage_"))
        ):
            arguments = nested_args

        return name, arguments

    def _compact_tool_result(self, result: MCPToolResult) -> str:
        if result.data is not None and not isinstance(result.data, str):
            text = json.dumps(
                result.data,
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )
        elif result.text:
            text = result.text
        elif result.data is not None:
            text = str(result.data)
        else:
            text = json.dumps(
                result.raw,
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )

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
            + "\n\nYou are the MCP planning stage. For every live-home question, use "
            "Ollama's native tool calling and call at least one relevant MCP tool before "
            "answering. Never print a tool request as JSON or prose. Never claim the hub is "
            "still gathering data unless an MCP result explicitly says that. Use "
            "hub_search_tools when the correct tool is unclear. Gateways may be called with "
            "no arguments to discover sub-tools, then with tool and args to execute one. "
            "Never use placeholders such as stale:N. Prefer the fewest focused calls and "
            "run them sequentially because the hub is resource constrained."
        )

    def _synthesis_messages(
        self,
        *,
        query: str,
        history: list[dict[str, str]],
        planner_messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        tool_context: list[dict[str, str]] = []
        for item in planner_messages:
            if item.get("role") == "tool":
                tool_context.append(
                    {
                        "role": "user",
                        "content": (
                            f"Authoritative MCP result from {item.get('tool_name', 'tool')}:\n"
                            f"{item.get('content', '')}"
                        ),
                    }
                )

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    KINGPANTHER_SYSTEM_PROMPT
                    + "\n\nYou are the final response stage. Answer the original question "
                    "naturally and directly using the authoritative MCP results below. Do not "
                    "output JSON, a tool request, tool names, schemas, planning notes, or options "
                    "for checks that have already been performed. Do not say data is still being "
                    "gathered when MCP data is present. Summarise the actual states, names, values, "
                    "warnings, or confirmed actions. If a particular fact is genuinely missing, "
                    "state only that limitation while still reporting everything that was found."
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
        messages.append(
            {
                "role": "user",
                "content": "Give the final user-facing answer now.",
            }
        )
        return messages

    @staticmethod
    def _requires_live_data(query: str) -> bool:
        q = str(query or "").lower()
        return any(
            term in q
            for term in (
                "home",
                "hub",
                "device",
                "light",
                "switch",
                "sensor",
                "thermostat",
                "battery",
                "weather",
                "rain",
                "temperature",
                "humidity",
                "room",
                "rule",
                "automation",
                "energy",
                "power",
                "presence",
                "motion",
                "door",
                "window",
                "lock",
                "heating",
                "attention",
                "offline",
                "stale",
            )
        )

    @staticmethod
    def _is_discovery_call(name: str, arguments: dict[str, Any]) -> bool:
        if name in {"hub_search_tools", "hub_get_tool_guide"}:
            return True
        return name.startswith(("hub_read_", "hub_manage_")) and not arguments

    @staticmethod
    def _tool_available(name: str, tools: list[MCPTool]) -> bool:
        return any(tool.name == name for tool in tools)

    @classmethod
    def _looks_like_tool_json(cls, content: str) -> bool:
        return bool(cls._extract_text_tool_calls(content))

    @staticmethod
    def _find_placeholder(value: Any) -> str | None:
        if isinstance(value, dict):
            for item in value.values():
                found = ClaudeStyleOllamaAgent._find_placeholder(item)
                if found:
                    return found
        elif isinstance(value, list):
            for item in value:
                found = ClaudeStyleOllamaAgent._find_placeholder(item)
                if found:
                    return found
        elif isinstance(value, str) and re.search(
            r"(?:^|[:=])(?:N|X|ID|NAME|VALUE)(?:$|[,}])",
            value,
            flags=re.IGNORECASE,
        ):
            return value
        return None

    @staticmethod
    def _model_matches(model: str, names: list[str]) -> bool:
        if not model:
            return False
        return model in names or any(
            name.split(":")[0] == model.split(":")[0] for name in names
        )


__all__ = ["ClaudeStyleOllamaAgent", "OllamaUnavailable"]
