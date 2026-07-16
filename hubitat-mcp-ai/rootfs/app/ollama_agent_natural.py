from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, Awaitable, Callable

from fallback_router import _device_id, _dicts, _label, _normalise
from fast_fallback_live import _looks_like_light, live_attributes
from mcp_client import HubitatMCPClient, MCPTool, MCPToolResult
from ollama_agent_claude import ClaudeStyleOllamaAgent
from ollama_agent_fast import OllamaUnavailable


FallbackProvider = Callable[[str], Awaitable[dict[str, Any]]]


class NaturalHubitatOllamaAgent(ClaudeStyleOllamaAgent):
    """Natural Ollama agent with bounded planning and MCP evidence recovery.

    Ollama remains responsible for understanding and wording natural questions.
    The deterministic fallback router is used only as an authoritative evidence
    provider when a small local planner cannot produce a valid MCP call quickly.
    Its pre-rendered response is never shown unless final synthesis also fails.
    """

    def __init__(
        self,
        client: HubitatMCPClient,
        base_url: str,
        model: str,
        *,
        fallback_provider: FallbackProvider | None = None,
        routine_model: str = "",
        routine_response_timeout_seconds: float = 55,
        evidence_item_limit: int = 10,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            client=client,
            base_url=base_url,
            model=model,
            **kwargs,
        )
        self.fallback_provider = fallback_provider
        self.configured_routine_model = str(routine_model or "").strip()
        self.routine_response_timeout_seconds = max(
            20.0,
            float(routine_response_timeout_seconds),
        )
        self.evidence_item_limit = max(4, int(evidence_item_limit))

    async def runtime_status(self, force: bool = False) -> dict[str, Any]:
        status = await super().runtime_status(force=force)
        installed = list(status.get("installed_models") or [])
        loaded = list(status.get("loaded_models") or [])
        routine = self._resolve_routine_model(installed)
        status["routine_model"] = routine
        status["routine_present"] = self._model_matches(routine, installed)
        status["routine_loaded"] = self._model_matches(routine, loaded)
        return status

    async def answer(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        history = history or []
        health = await self.health()
        if not health.get("online"):
            raise OllamaUnavailable(health.get("error") or "Ollama is offline")
        if health.get("model_present") is False:
            raise OllamaUnavailable(
                f"Configured Ollama model {self.model} is not installed."
            )

        installed = list(health.get("models") or [])
        planner_model = self._resolve_planner_model(installed)
        deep_reasoning = self._is_deep_reasoning_query(query)
        response_model = (
            self.model if deep_reasoning else self._resolve_routine_model(installed)
        )
        response_timeout = (
            self.response_timeout_seconds
            if deep_reasoning
            else min(
                self.response_timeout_seconds,
                self.routine_response_timeout_seconds,
            )
        )
        planning_timeout = min(
            self.planner_timeout_seconds,
            35.0 if deep_reasoning else 25.0,
        )

        tools = await self.client.list_tools()
        selected = self._select_compact_tools(query, tools)
        ollama_tools = [tool.as_ollama_tool() for tool in selected]

        self._last_agent_status = {
            "state": "planning",
            "planner_model": planner_model,
            "response_model": response_model,
            "query": query[:200],
            "started_at": time.time(),
        }

        phase_ms: dict[str, int] = {}
        tools_used: list[dict[str, Any]] = []
        evidence: list[dict[str, str]] = []
        fallback_answer: dict[str, Any] | None = None
        planner_error: str | None = None

        planning_started = time.perf_counter()
        try:
            evidence, tools_used = await self._plan_and_collect(
                query=query,
                history=history,
                planner_model=planner_model,
                selected=selected,
                ollama_tools=ollama_tools,
                timeout_seconds=planning_timeout,
            )
        except Exception as exc:
            planner_error = str(exc) or exc.__class__.__name__
        phase_ms["planning"] = round(
            (time.perf_counter() - planning_started) * 1000
        )

        if not evidence:
            fallback_started = time.perf_counter()
            fallback_answer = await self._fallback_evidence(query)
            phase_ms["mcp_recovery"] = round(
                (time.perf_counter() - fallback_started) * 1000
            )
            if fallback_answer is not None:
                evidence = [
                    {
                        "tool": "verified_mcp_context",
                        "content": self._compact_fallback_evidence(fallback_answer),
                    }
                ]

        if not evidence:
            detail = planner_error or "No authoritative MCP evidence was returned."
            raise OllamaUnavailable(
                f"The natural agent could not obtain live Hubitat data: {detail}"
            )

        self._last_agent_status["state"] = "synthesising"
        synthesis_started = time.perf_counter()
        try:
            body = await self._chat(
                model=response_model,
                messages=self._evidence_messages(
                    query=query,
                    history=history,
                    evidence=evidence,
                ),
                tools=None,
                timeout_seconds=response_timeout,
                num_ctx=min(self.num_ctx, 4096 if deep_reasoning else 3072),
                num_predict=min(self.num_predict, 220 if deep_reasoning else 140),
                temperature=0.25,
            )
            content = str((body.get("message") or {}).get("content") or "").strip()
            if not content or self._looks_like_tool_json(content):
                raise OllamaUnavailable(
                    "Ollama did not return a usable final user-facing answer."
                )
        except Exception as exc:
            phase_ms["synthesis"] = round(
                (time.perf_counter() - synthesis_started) * 1000
            )
            if fallback_answer is not None:
                return self._compact_fallback_result(
                    fallback_answer,
                    started=started,
                    planner_error=planner_error,
                    synthesis_error=str(exc),
                    planner_model=planner_model,
                    response_model=response_model,
                    phase_ms=phase_ms,
                )
            if isinstance(exc, OllamaUnavailable):
                raise
            raise OllamaUnavailable(str(exc)) from exc

        phase_ms["synthesis"] = round(
            (time.perf_counter() - synthesis_started) * 1000
        )
        elapsed = round((time.perf_counter() - started) * 1000)
        self.record_inference_success(elapsed, source="natural-agent")
        self._last_agent_status = {
            "state": "ready",
            "planner_model": planner_model,
            "response_model": response_model,
            "tools_used": [item.get("name") for item in tools_used],
            "evidence_source": (
                "mcp-recovery" if fallback_answer is not None else "ollama-planner"
            ),
            "phase_ms": dict(phase_ms),
            "elapsed_ms": elapsed,
            "completed_at": time.time(),
        }
        return {
            "success": True,
            "route": "ollama+mcp",
            "intent": "ollama-natural-agent",
            "message": content,
            "model": response_model,
            "planner_model": planner_model,
            "response_model": response_model,
            "tools_used": tools_used,
            "selected_tools": [tool.name for tool in selected],
            "evidence_source": (
                "mcp-recovery" if fallback_answer is not None else "ollama-planner"
            ),
            "planner_error": planner_error,
            "phase_ms": phase_ms,
            "elapsed_ms": elapsed,
        }

    async def _plan_and_collect(
        self,
        *,
        query: str,
        history: list[dict[str, str]],
        planner_model: str,
        selected: list[MCPTool],
        ollama_tools: list[dict[str, Any]],
        timeout_seconds: float,
    ) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._planner_prompt()}
        ]
        for item in history[-6:]:
            role = item.get("role")
            content = item.get("content")
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": str(content)})
        messages.append({"role": "user", "content": query})

        body = await self._chat(
            model=planner_model,
            messages=messages,
            tools=ollama_tools,
            timeout_seconds=timeout_seconds,
            num_ctx=min(self.num_ctx, 3072),
            num_predict=min(self.num_predict, 120),
            temperature=0.05,
        )
        message = body.get("message") or {}
        planning_content = str(message.get("content") or "").strip()
        tool_calls = list(message.get("tool_calls") or [])
        if not tool_calls and planning_content:
            tool_calls = self._extract_text_tool_calls(planning_content)

        normalised: list[dict[str, Any]] = []
        for tool_call in tool_calls:
            name, arguments = self._parse_tool_call(tool_call)
            if name:
                normalised.append(
                    {
                        "function": {
                            "name": name,
                            "arguments": arguments,
                        }
                    }
                )

        evidence: list[dict[str, str]] = []
        records: list[dict[str, Any]] = []
        for tool_call in normalised[:3]:
            name, arguments = self._parse_tool_call(tool_call)
            record, tool_text = await self._execute_tool_call_for_query(
                name=name,
                arguments=arguments,
                query=query,
            )
            records.append(record)
            if record.get("success") and not self._is_discovery_call(name, arguments):
                evidence.append({"tool": name, "content": tool_text})

        return evidence, records

    async def _execute_tool_call_for_query(
        self,
        *,
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
            text = f"Invalid unresolved placeholder: {placeholder}"
            return {
                "name": name,
                "arguments": arguments,
                "success": False,
                "error": text,
            }, text

        if self._sensitive_confirmation_required(name, arguments, query):
            text = (
                "This operation requires explicit confirmation in the user's latest "
                "message."
            )
            return {
                "name": name,
                "arguments": arguments,
                "success": False,
                "blocked": "confirmation-required",
            }, text

        try:
            result = await self.client.call_tool(name, arguments)
            tool_text = self._compact_result_for_query(
                query=query,
                tool_name=name,
                result=result,
            )
            return {
                "name": name,
                "arguments": arguments,
                "success": not result.is_error,
                "preview": tool_text[:700],
            }, tool_text
        except Exception as exc:
            text = f"MCP tool error: {exc}"
            return {
                "name": name,
                "arguments": arguments,
                "success": False,
                "error": str(exc),
            }, text

    async def _fallback_evidence(self, query: str) -> dict[str, Any] | None:
        if self.fallback_provider is None:
            return None
        timeout = max(
            8.0,
            float(getattr(self.client, "timeout_seconds", 25)) + 5.0,
        )
        try:
            response = await asyncio.wait_for(
                self.fallback_provider(query),
                timeout=timeout,
            )
        except Exception:
            return None
        if not isinstance(response, dict):
            return None
        if response.get("intent") in {"fallback-unsupported", "fallback-error"}:
            return None
        return response

    def _compact_result_for_query(
        self,
        *,
        query: str,
        tool_name: str,
        result: MCPToolResult,
    ) -> str:
        if result.is_error:
            return result.text or f"{tool_name} returned an error."

        device_rows = self._device_rows_from_data(result.data)
        if device_rows:
            return json.dumps(
                self._device_evidence(query, device_rows),
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )

        value = result.data
        if value is None:
            value = result.text or result.raw
        text = (
            value
            if isinstance(value, str)
            else json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )
        )
        return self._bounded_text(str(text), self.tool_result_limit_chars)

    def _device_evidence(
        self,
        query: str,
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        q = _normalise(query)
        lights_on: list[str] = []
        switches_on: list[str] = []
        motion_active: list[str] = []
        low_batteries: list[dict[str, Any]] = []
        offline: list[str] = []
        present: list[str] = []
        temperatures: list[dict[str, Any]] = []
        weather_devices: list[dict[str, Any]] = []
        generic: list[dict[str, Any]] = []

        for item in rows:
            label = _label(item) or str(_device_id(item) or "Unknown device")
            attrs = live_attributes(item)
            switch = _normalise(attrs.get("switch"))
            if switch == "on":
                if _looks_like_light(item):
                    lights_on.append(label)
                else:
                    switches_on.append(label)
            if _normalise(attrs.get("motion")) == "active":
                motion_active.append(label)
            battery = self._number(attrs.get("battery"))
            if battery is not None and battery <= 20:
                low_batteries.append({"name": label, "battery": battery})
            health = _normalise(
                attrs.get("healthStatus")
                or attrs.get("status")
                or item.get("healthStatus")
                or item.get("status")
            )
            if health in {
                "offline",
                "unavailable",
                "not present",
                "dead",
                "failed",
            }:
                offline.append(label)
            if _normalise(attrs.get("presence")) == "present":
                present.append(label)
            temperature = self._number(attrs.get("temperature"))
            if temperature is not None:
                temperatures.append({"name": label, "temperature": temperature})

            searchable = _normalise(
                f"{label} {item.get('type', '')} {item.get('deviceType', '')}"
            )
            if "weather" in searchable:
                selected_attrs = {
                    key: value
                    for key, value in attrs.items()
                    if any(
                        term in key.lower()
                        for term in (
                            "weather",
                            "forecast",
                            "rain",
                            "precip",
                            "condition",
                            "temperature",
                            "humidity",
                            "high",
                            "low",
                        )
                    )
                }
                weather_devices.append(
                    {
                        "name": label,
                        "attributes": dict(list(selected_attrs.items())[:40]),
                    }
                )

            if len(generic) < 20:
                useful_attrs = {
                    key: value
                    for key, value in attrs.items()
                    if key
                    in {
                        "switch",
                        "level",
                        "motion",
                        "contact",
                        "temperature",
                        "humidity",
                        "battery",
                        "presence",
                        "healthStatus",
                        "status",
                        "thermostatMode",
                        "heatingSetpoint",
                    }
                }
                generic.append(
                    {
                        "name": label,
                        "room": item.get("room"),
                        "attributes": useful_attrs,
                    }
                )

        lights_on = sorted(dict.fromkeys(lights_on), key=str.lower)
        switches_on = sorted(dict.fromkeys(switches_on), key=str.lower)
        motion_active = sorted(dict.fromkeys(motion_active), key=str.lower)
        offline = sorted(dict.fromkeys(offline), key=str.lower)
        present = sorted(dict.fromkeys(present), key=str.lower)
        low_batteries.sort(key=lambda item: (item["battery"], item["name"].lower()))

        evidence: dict[str, Any] = {
            "device_count_read": len(rows),
            "counts": {
                "lights_on": len(lights_on),
                "other_switches_on": len(switches_on),
                "motion_active": len(motion_active),
                "low_batteries": len(low_batteries),
                "offline": len(offline),
                "present": len(present),
            },
        }

        if any(term in q for term in ("weather", "rain", "forecast", "outside")):
            evidence["weather_devices"] = weather_devices[:3]
        elif any(term in q for term in ("attention", "offline", "stale", "battery")):
            evidence.update(
                {
                    "low_batteries": low_batteries[:12],
                    "offline_devices": offline[:12],
                    "devices": generic[:12],
                }
            )
        elif any(
            term in q
            for term in (
                "what's happening",
                "what is happening",
                "home status",
                "at home",
            )
        ):
            evidence.update(
                {
                    "lights_on": lights_on[:12],
                    "motion_active": motion_active[:12],
                    "low_batteries": low_batteries[:12],
                    "people_or_presence_present": present[:12],
                    "other_switches_on_count": len(switches_on),
                    "other_switches_note": (
                        "Always-on plugs and infrastructure switches are counted but "
                        "their full list is intentionally omitted from the overview."
                    ),
                }
            )
        elif "light" in q:
            evidence["lights_on"] = lights_on[:30]
        elif "switch" in q:
            evidence["switches_on"] = switches_on[:30]
        elif "temperature" in q or "heating" in q:
            evidence["temperatures"] = temperatures[:20]
            evidence["devices"] = generic[:12]
        else:
            evidence["devices"] = generic[:20]

        return evidence

    def _compact_fallback_evidence(self, response: dict[str, Any]) -> str:
        display = response.get("display")
        display = display if isinstance(display, dict) else {}
        metrics = display.get("metrics")
        metrics = metrics if isinstance(metrics, list) else []
        items = display.get("items")
        items = items if isinstance(items, list) else []

        selected_items = self._prioritise_display_items(items)
        payload = {
            "title": display.get("title"),
            "subtitle": display.get("subtitle"),
            "metrics": metrics[:8],
            "important_items": selected_items,
            "omitted_item_count": max(0, len(items) - len(selected_items)),
            "note": display.get("note"),
        }
        if not metrics and not selected_items:
            payload["summary"] = self._bounded_text(
                str(response.get("message") or ""),
                2500,
            )
        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )

    def _compact_fallback_result(
        self,
        response: dict[str, Any],
        *,
        started: float,
        planner_error: str | None,
        synthesis_error: str,
        planner_model: str,
        response_model: str,
        phase_ms: dict[str, int],
    ) -> dict[str, Any]:
        answer = dict(response)
        display = answer.get("display")
        if isinstance(display, dict):
            display = dict(display)
            items = display.get("items")
            if isinstance(items, list):
                selected = self._prioritise_display_items(items)
                omitted = max(0, len(items) - len(selected))
                display["items"] = selected
                note = str(display.get("note") or "").strip()
                if omitted:
                    note = (
                        note + " " if note else ""
                    ) + f"{omitted} routine items were omitted from this overview."
                display["note"] = note
            answer["display"] = display

        answer["route"] = "fallback-compact"
        answer["ollama_error"] = synthesis_error
        answer["planner_error"] = planner_error
        answer["planner_model"] = planner_model
        answer["response_model"] = response_model
        answer["phase_ms"] = phase_ms
        answer["elapsed_ms"] = round((time.perf_counter() - started) * 1000)
        return answer

    def _evidence_messages(
        self,
        *,
        query: str,
        history: list[dict[str, str]],
        evidence: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "You are a natural, concise local smart-home assistant. The evidence "
                    "below came from kingpanther13's live Hubitat MCP server and is "
                    "authoritative. Lead with what matters now. Do not mention JSON, tools, "
                    "routing, fallback, planning, or missing checks that were already run. "
                    "For a home overview, prioritise lights, active motion/presence, low "
                    "batteries, offline devices, warnings and unusual conditions. Do not "
                    "list every always-on socket, camera or infrastructure switch unless "
                    "the user asks for that list. Never invent a state or action."
                ),
            }
        ]
        for item in history[-4:]:
            if item.get("role") in {"user", "assistant"} and item.get("content"):
                messages.append(
                    {"role": item["role"], "content": str(item["content"])}
                )
        messages.append({"role": "user", "content": query})
        for item in evidence:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Authoritative Hubitat evidence ({item['tool']}):\n"
                        f"{item['content']}"
                    ),
                }
            )
        messages.append(
            {
                "role": "user",
                "content": "Answer the original question naturally now.",
            }
        )
        return messages

    def _select_compact_tools(
        self,
        query: str,
        tools: list[MCPTool],
    ) -> list[MCPTool]:
        selected = super()._select_compact_tools(query, tools)
        discovery_names = {"hub_search_tools", "hub_get_tool_guide"}
        direct = [tool for tool in selected if tool.name not in discovery_names]

        q = _normalise(query)
        needs_catalogue = any(
            term in q
            for term in (
                "create rule",
                "create automation",
                "modify rule",
                "change rule",
                "delete rule",
                "which tool",
                "what tools",
            )
        )
        if direct and not needs_catalogue:
            return direct[: min(self.planner_tool_limit, 4)]
        return selected[: min(self.planner_tool_limit, 4)]

    def _resolve_routine_model(self, installed_models: list[str]) -> str:
        if self.configured_routine_model:
            if self._model_matches(self.configured_routine_model, installed_models):
                return self.configured_routine_model
            return self.model
        return self._resolve_planner_model(installed_models)

    @staticmethod
    def _is_deep_reasoning_query(query: str) -> bool:
        q = _normalise(query)
        return any(
            term in q
            for term in (
                "why ",
                "explain",
                "analyse",
                "analyze",
                "compare",
                "correlate",
                "recommend",
                "suggest",
                "diagnose",
                "troubleshoot",
                "create rule",
                "create automation",
                "modify rule",
                "optimise",
                "optimize",
                "pattern",
                "trend",
            )
        )

    def _prioritise_display_items(
        self,
        items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        def score(item: dict[str, Any]) -> tuple[int, str]:
            tone = _normalise(item.get("tone"))
            icon = str(item.get("icon") or "")
            value = _normalise(item.get("value"))
            priority = 40
            if tone == "danger":
                priority = 0
            elif tone == "warning":
                priority = 5
            elif "🪫" in icon or "📡" in icon or "⚠" in icon:
                priority = 8
            elif "💡" in icon:
                priority = 12
            elif "🏃" in icon:
                priority = 16
            elif "🔌" in icon and value == "on":
                priority = 60
            return priority, _normalise(item.get("title"))

        ordered = sorted(
            [dict(item) for item in items if isinstance(item, dict)],
            key=score,
        )
        return ordered[: self.evidence_item_limit]

    @staticmethod
    def _device_rows_from_data(data: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in _dicts(data):
            if not any(key in item for key in ("id", "deviceId", "device_id")):
                continue
            if not any(
                key in item for key in ("label", "displayName", "name", "deviceLabel")
            ):
                continue
            device_id = str(_device_id(item) or _label(item))
            if not device_id or device_id in seen:
                continue
            seen.add(device_id)
            rows.append(item)
        return rows

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            return float(str(value).replace("%", "").strip())
        except Exception:
            return None

    @staticmethod
    def _bounded_text(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        head = int(limit * 0.8)
        return text[:head] + "\n...[evidence compacted]...\n" + text[-(limit - head):]


__all__ = ["NaturalHubitatOllamaAgent", "OllamaUnavailable"]
