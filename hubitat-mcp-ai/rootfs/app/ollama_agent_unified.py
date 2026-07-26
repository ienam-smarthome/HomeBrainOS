from __future__ import annotations

import asyncio
import json
import re
import time
from collections import Counter
from contextvars import ContextVar
from typing import Any, Awaitable, Callable

from device_intelligence_index import _attributes, _device_id, _device_rows, _label, _room_name
from fallback_router import _device_id as _fallback_device_id, _dicts, _label as _fallback_label, _normalise
from fast_fallback_live import _looks_like_light, live_attributes
from mcp_client import MCPTool, MCPToolResult
from ollama_agent_claude import ClaudeStyleOllamaAgent
from ollama_agent_claude import ClaudeStyleOllamaAgent
from ollama_agent_fast import OllamaUnavailable
from ollama_hybrid_http import HybridOllamaHTTPClient
from routing_policy import requires_planner


_TARGETED_DEVICE_SEARCH = "homebrain_search_devices"
_DISCOVERY_TOOLS = {
    _TARGETED_DEVICE_SEARCH,
    "hub_search_tools",
    "hub_get_tool_guide",
    "hub_list_devices",
    "hub_read_devices",
}
_GENERIC_DEVICE_QUERY_WORDS = {
    "all",
    "any",
    "available",
    "device",
    "devices",
    "discover",
    "find",
    "get",
    "inventory",
    "list",
    "my",
    "please",
    "selected",
    "show",
    "the",
}
_TARGETED_DEVICE_LOOKUP = re.compile(
    r"^(?:please\s+)?(?:find|search(?:\s+for)?|locate|look\s+(?:up|for)|"
    r"show\s+(?:me\s+)?(?:matches\s+for\s+)?)(?:the\s+)?(?:device\s+)?(.+?)[.!?]*$",
    re.IGNORECASE,
)


def _normalise_words(value: str) -> list[str]:
    return [item for item in re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).split() if item]


_TARGET_LOCAL_MODEL_BILLIONS = 4.0

_CHAT_MODEL_USED: ContextVar[str | None] = ContextVar(
    "homebrain_ollama_model_used",
    default=None,
)

_CHAT_PROVIDER_USED: ContextVar[str | None] = ContextVar(
    "homebrain_ollama_provider_used",
    default=None,
)

_CHAT_CLOUD_ERROR: ContextVar[str | None] = ContextVar(
    "homebrain_ollama_cloud_error",
    default=None,
)


_FINAL_ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {
            "type": "string",
            "description": "The complete user-facing answer only, with no analysis or hidden reasoning.",
        }
    },
    "required": ["answer"],
    "additionalProperties": False,
}

_REASONING_PATTERNS = (
    r"<think>",
    r"\bthe user (?:asked|wants|requested)\b",
    r"\bi have (?:the )?verified .* evidence\b",
    r"\bthe evidence (?:shows|contains|says|indicates)\b",
    r"\blet me (?:check|parse|think|tackle|analyse|analyze|work)\b",
    r"\bfirst,? i (?:need|should|will)\b",
    r"\bnext,? i (?:need|should|will)\b",
    r"\bwait,? (?:the user|i need|the evidence)\b",
    r"\bi should (?:answer|highlight|mention|focus|summarise|summarize)\b",
    r"\bso the key points\b",
    r"^analysis\s*:",
)


FallbackProvider = Callable[[str], Awaitable[dict[str, Any]]]


class UnifiedAdaptiveMCPAgent(ClaudeStyleOllamaAgent):
    """AI-first Hubitat agent with structured device resolution."""

    def __init__(
        self,
        *args: Any,
        fallback_provider: FallbackProvider | None = None,
        routine_model: str = "",
        routine_response_timeout_seconds: float = 55,
        evidence_item_limit: int = 10,
        unified_tool_limit: int = 48,
        cloud_enabled: bool = False,
        cloud_model: str = "",
        local_fallback_model: str = "",
        cloud_fallback_local: bool = True,
        cloud_timeout_seconds: float = 25.0,
        direct_cloud_enabled: bool = False,
        direct_cloud_base_url: str = "https://ollama.com",
        direct_cloud_api_key: str = "",
        direct_cloud_model: str = "",
        direct_cloud_fallback_local_proxy: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)

        self.fallback_provider = fallback_provider
        self.configured_routine_model = str(
            routine_model or ""
        ).strip()
        self.routine_response_timeout_seconds = max(
            20.0,
            float(routine_response_timeout_seconds),
        )
        self.evidence_item_limit = max(
            4,
            int(evidence_item_limit),
        )

        self.unified_tool_limit = max(
            16,
            min(96, int(unified_tool_limit)),
        )

        self.cloud_enabled = bool(cloud_enabled)
        self.cloud_model = str(cloud_model or "").strip()
        self.local_fallback_model = str(
            local_fallback_model or ""
        ).strip()
        self.cloud_fallback_local = bool(
            cloud_fallback_local
        )
        self.cloud_timeout_seconds = max(
            8.0,
            min(90.0, float(cloud_timeout_seconds)),
        )
        self._cloud_present_hint: bool | None = None

        existing_http = self._http
        self._http = HybridOllamaHTTPClient(
            local_base_url=self.base_url,
            cloud_model=self.cloud_model,
            direct_enabled=bool(direct_cloud_enabled),
            direct_base_url=str(
                direct_cloud_base_url or "https://ollama.com"
            ),
            direct_api_key=str(
                direct_cloud_api_key or ""
            ),
            direct_model=str(
                direct_cloud_model or ""
            ),
            fallback_local_proxy=bool(
                direct_cloud_fallback_local_proxy
            ),
            client=existing_http,
        )

    def _exact_model_present(model: str, installed_models: list[str]) -> bool:
        target = str(model or "").strip().lower()
        return bool(target) and any(
            str(name or "").strip().lower() == target for name in installed_models
        )

    def _cloud_model_present(self, installed_models: list[str]) -> bool:
        return bool(
            self.cloud_enabled
            and self.cloud_model
            and self._exact_model_present(self.cloud_model, installed_models)
        )

    async def health(self, force: bool = False) -> dict[str, Any]:
        status = await super().health(force=force)
        transport = self._http
        if not status.get("online"):
            result = dict(status)
            result.update(
                {
                    "direct_cloud_enabled": bool(transport.direct_enabled),
                    "direct_cloud_ready": bool(transport.direct_ready),
                    "direct_cloud_api_key_configured": bool(
                        transport.direct_api_key_configured
                    ),
                    "direct_cloud_model": transport.direct_model or None,
                    "direct_cloud_error": transport.last_direct_error,
                }
            )
            return result

        installed = list(status.get("models") or [])
        cloud_present = self._cloud_model_present(installed)
        local_present = self._exact_model_present(
            self.local_fallback_model,
            installed,
        )
        self._cloud_present_hint = cloud_present

        result = dict(status)
        result["model_present"] = bool(cloud_present or local_present)
        result["cloud_present"] = cloud_present
        result["local_fallback_present"] = local_present
        result["cloud_model"] = self.cloud_model or None
        result["local_fallback_model"] = self.local_fallback_model or None
        result["direct_cloud_enabled"] = bool(transport.direct_enabled)
        result["direct_cloud_ready"] = bool(transport.direct_ready)
        result["direct_cloud_api_key_configured"] = bool(
            transport.direct_api_key_configured
        )
        result["direct_cloud_base_url"] = transport.direct_base_url or None
        result["direct_cloud_model"] = transport.direct_model or None
        result["direct_cloud_error"] = transport.last_direct_error
        result["ollama_provider"] = transport.last_provider()
        return result

    async def runtime_status(self, force: bool = False) -> dict[str, Any]:
        status = await super().runtime_status(force=force)
        installed = list(status.get("installed_models") or [])
        loaded = list(status.get("loaded_models") or [])

        routine = self._resolve_routine_model(installed)
        status["routine_model"] = routine
        status["routine_present"] = self._model_matches(
            routine,
            installed,
        )
        status["routine_loaded"] = self._model_matches(
            routine,
            loaded,
        )

        cloud_present = self._cloud_model_present(installed)
        local_present = self._exact_model_present(
            self.local_fallback_model,
            installed,
        )
        transport = self._http
        status.update(
            {
                "cloud_enabled": self.cloud_enabled,
                "cloud_model": self.cloud_model or None,
                "cloud_present": cloud_present,
                "local_fallback_model": self.local_fallback_model or None,
                "local_fallback_present": local_present,
                "cloud_fallback_local": self.cloud_fallback_local,
                "direct_cloud_enabled": bool(transport.direct_enabled),
                "direct_cloud_ready": bool(transport.direct_ready),
                "direct_cloud_api_key_configured": bool(
                    transport.direct_api_key_configured
                ),
                "direct_cloud_base_url": transport.direct_base_url or None,
                "direct_cloud_model": transport.direct_model or None,
                "direct_cloud_fallback_local_proxy": bool(
                    transport.fallback_local_proxy
                ),
                "direct_cloud_error": transport.last_direct_error,
                "ollama_provider": transport.last_provider(),
                "preferred_response_model": (
                    self.cloud_model
                    if cloud_present
                    else self.local_fallback_model
                    if local_present
                    else self.model
                ),
            }
        )
        return status

    async def _natural_answer(
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
            label = _fallback_label(item) or str(_fallback_device_id(item) or "Unknown device")
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
            device_id = str(_fallback_device_id(item) or _fallback_label(item))
            if not device_id or device_id in seen:
                continue
            seen.add(device_id)
            rows.append(item)
        return rows

    def _number(value: Any) -> float | None:
        try:
            return float(str(value).replace("%", "").strip())
        except Exception:
            return None

    def _bounded_text(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        head = int(limit * 0.8)
        return text[:head] + "\n...[evidence compacted]...\n" + text[-(limit - head):]

    async def _quality_answer(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        history = history or []
        if requires_planner(query):
            return await self._natural_answer(query, history)

        verified = await self._fallback_evidence(query)
        if verified is not None:
            return await self._answer_from_verified_context(
                query=query,
                history=history,
                verified=verified,
            )
        return await self._natural_answer(query, history)

    def _resolve_planner_model(self, installed_models: list[str]) -> str:
        if self.configured_planner_model:
            if self._model_matches(self.configured_planner_model, installed_models):
                return self.configured_planner_model
            return self.model
        return self._preferred_family_model(installed_models)

    def _resolve_routine_model(self, installed_models: list[str]) -> str:
        if self.configured_routine_model:
            if self._model_matches(self.configured_routine_model, installed_models):
                return self.configured_routine_model
            return self.model
        return self._preferred_family_model(installed_models)

    async def _answer_from_verified_context(
        self,
        *,
        query: str,
        history: list[dict[str, str]],
        verified: dict[str, Any],
    ) -> dict[str, Any]:
        started = time.perf_counter()
        health = await self.health()
        if not health.get("online"):
            raise OllamaUnavailable(health.get("error") or "Ollama is offline")
        if health.get("model_present") is False:
            raise OllamaUnavailable(
                f"Configured Ollama model {self.model} is not installed."
            )

        installed = list(health.get("models") or [])
        response_model = self._resolve_routine_model(installed)
        evidence_text = self._compact_fallback_evidence(verified)
        timeout = min(
            self.response_timeout_seconds,
            self.routine_response_timeout_seconds,
            40.0,
        )

        self._last_agent_status = {
            "state": "synthesising",
            "planner_model": "verified-mcp-context",
            "response_model": response_model,
            "query": query[:200],
            "evidence_source": "verified-mcp-context",
            "started_at": time.time(),
        }

        synthesis_started = time.perf_counter()
        try:
            body = await self._chat(
                model=response_model,
                messages=self._verified_messages(
                    query=query,
                    history=history,
                    evidence=evidence_text,
                ),
                tools=None,
                timeout_seconds=timeout,
                num_ctx=min(self.num_ctx, 2048),
                num_predict=min(self.num_predict, 120),
                temperature=0.1,
            )
            content = str((body.get("message") or {}).get("content") or "").strip()
            if self._unreliable_verified_answer(query, content, evidence_text):
                raise OllamaUnavailable(
                    "Ollama added unsupported claims to verified Hubitat evidence."
                )
        except Exception as exc:
            phase_ms = {
                "mcp_context": 0,
                "synthesis": round((time.perf_counter() - synthesis_started) * 1000),
            }
            return self._compact_fallback_result(
                verified,
                started=started,
                planner_error=None,
                synthesis_error=str(exc),
                planner_model="verified-mcp-context",
                response_model=response_model,
                phase_ms=phase_ms,
            )

        elapsed = round((time.perf_counter() - started) * 1000)
        self.record_inference_success(elapsed, source="verified-natural-agent")
        self._last_agent_status = {
            "state": "ready",
            "planner_model": "verified-mcp-context",
            "response_model": response_model,
            "tools_used": ["verified_mcp_context"],
            "evidence_source": "verified-mcp-context",
            "phase_ms": {"synthesis": elapsed},
            "elapsed_ms": elapsed,
            "completed_at": time.time(),
        }
        return {
            "success": True,
            "route": "ollama+mcp",
            "intent": "ollama-verified-natural-agent",
            "message": content,
            "model": response_model,
            "planner_model": "verified-mcp-context",
            "response_model": response_model,
            "tools_used": [
                {
                    "name": "verified_mcp_context",
                    "success": True,
                    "preview": evidence_text[:700],
                }
            ],
            "selected_tools": ["verified_mcp_context"],
            "evidence_source": "verified-mcp-context",
            "phase_ms": {"synthesis": elapsed},
            "elapsed_ms": elapsed,
        }

    def _verified_messages(
        *,
        query: str,
        history: list[dict[str, str]],
        evidence: str,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "You are a concise, natural local smart-home assistant. Use only the "
                    "verified Hubitat evidence supplied below. It is complete enough to answer "
                    "the question. Never invent firmware, backups, timestamps, temperatures, "
                    "alerts, occupancy or device states. Hub internal temperature is not home "
                    "temperature. A zero or missing timestamp is not a real event. Lead with "
                    "what matters now, name important devices, and keep routine answers to two "
                    "to four short sentences. Do not offer a numbered menu or ask a follow-up "
                    "question unless the evidence is genuinely ambiguous."
                ),
            }
        ]
        for item in history[-2:]:
            if item.get("role") in {"user", "assistant"} and item.get("content"):
                messages.append(
                    {"role": str(item["role"]), "content": str(item["content"])}
                )
        messages.extend(
            [
                {"role": "user", "content": query},
                {
                    "role": "user",
                    "content": "Verified live Hubitat evidence:\n" + evidence,
                },
                {
                    "role": "user",
                    "content": "Answer the original question now using only that evidence.",
                },
            ]
        )
        return messages

    def _unreliable_verified_answer(
        self,
        query: str,
        content: str,
        evidence: str,
    ) -> bool:
        if not content or self._looks_like_tool_json(content):
            return True
        text = content.lower()
        evidence_lower = evidence.lower()
        blocked = (
            "epoch 0",
            "hub is still gathering data",
            "i don't have enough information",
            "i do not have enough information",
            "can't confirm device states",
            "cannot confirm device states",
        )
        if any(phrase in text for phrase in blocked):
            return True

        q = query.lower()
        is_home_overview = any(
            phrase in q
            for phrase in (
                "what's happening",
                "what is happening",
                "home status",
                "at home",
            )
        )
        if is_home_overview:
            for unsupported in ("firmware", "backup", "epoch"):
                if unsupported in text and unsupported not in evidence_lower:
                    return True
            if (
                re.search(r"\b4[0-9](?:\.\d+)?\s*(?:°\s*c|degrees? celsius)", text)
                and "temperature" not in evidence_lower
            ):
                return True
        return False

    async def answer(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        model_token = _CHAT_MODEL_USED.set(None)
        provider_token = _CHAT_PROVIDER_USED.set(None)
        error_token = _CHAT_CLOUD_ERROR.set(None)
        try:
            result = dict(await self._quality_answer(query, history or []))
            actual_model = _CHAT_MODEL_USED.get()
            provider = _CHAT_PROVIDER_USED.get()
            cloud_error = _CHAT_CLOUD_ERROR.get()
            if actual_model and str(result.get("route") or "").startswith("ollama"):
                result["model"] = actual_model
                if "response_model" in result:
                    result["response_model"] = actual_model
                result["ai_provider"] = provider
                if cloud_error:
                    result["cloud_fallback_error"] = cloud_error
            return result
        finally:
            _CHAT_MODEL_USED.reset(model_token)
            _CHAT_PROVIDER_USED.reset(provider_token)
            _CHAT_CLOUD_ERROR.reset(error_token)

    async def _final_answer_chat(
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
        # Planning calls still need native tool_calls and therefore use the base
        # implementation unchanged. Only final user-facing synthesis is forced
        # through a strict answer schema.
        if tools:
            return await super()._chat(
                model=model,
                messages=messages,
                tools=tools,
                timeout_seconds=timeout_seconds,
                num_ctx=num_ctx,
                num_predict=num_predict,
                temperature=temperature,
            )

        final_messages = self._final_only_messages(messages)
        try:
            body = await self._structured_final_chat(
                model=model,
                messages=final_messages,
                timeout_seconds=timeout_seconds,
                num_ctx=num_ctx,
                num_predict=max(160, num_predict),
            )
            answer = self._extract_final_answer(body, require_json=True)
        except OllamaUnavailable as structured_error:
            # Older Ollama builds may not support JSON-schema output. Keep a
            # compatibility path, but still reject any visible chain-of-thought.
            try:
                body = await super()._chat(
                    model=model,
                    messages=final_messages,
                    tools=None,
                    timeout_seconds=timeout_seconds,
                    num_ctx=num_ctx,
                    num_predict=max(160, num_predict),
                    temperature=0.0,
                )
                answer = self._extract_final_answer(body, require_json=False)
            except Exception as fallback_error:
                raise OllamaUnavailable(
                    f"Final-answer generation failed: {structured_error}; {fallback_error}"
                ) from fallback_error

        clean_body = dict(body)
        message = dict(clean_body.get("message") or {})
        message["content"] = answer
        message.pop("thinking", None)
        clean_body["message"] = message
        return clean_body

    async def _structured_final_chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        timeout_seconds: float,
        num_ctx: int,
        num_predict: int,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": False,
            "format": _FINAL_ANSWER_SCHEMA,
            "keep_alive": self.keep_alive,
            "options": {
                "num_ctx": num_ctx,
                "num_predict": num_predict,
                "temperature": 0,
            },
        }
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
            raise OllamaUnavailable(
                f"Ollama structured final answer failed for {model}: {text}"
            ) from exc

    def _final_only_messages(
        cls,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        instruction = (
            "/no_think\n"
            "Return only the final answer for the user. Do not reveal analysis, planning, "
            "evidence parsing, hidden reasoning, or phrases such as 'the user asked'. "
            "The response must match the supplied JSON schema exactly: "
            '{"answer":"complete user-facing answer"}.'
        )
        cleaned: list[dict[str, Any]] = []
        system_found = False
        for raw in messages:
            item = dict(raw)
            role = str(item.get("role") or "")
            content = str(item.get("content") or "")
            if role == "assistant" and cls._looks_like_reasoning(content):
                # Do not feed a leaked reasoning response back into the next turn.
                continue
            if role == "system":
                system_found = True
                item["content"] = (content.rstrip() + "\n\n" + instruction).strip()
            cleaned.append(item)
        if not system_found:
            cleaned.insert(0, {"role": "system", "content": instruction})
        return cleaned

    def _extract_final_answer(
        cls,
        body: dict[str, Any],
        *,
        require_json: bool,
    ) -> str:
        if str(body.get("done_reason") or "").lower() == "length":
            raise OllamaUnavailable("Ollama final answer was truncated")

        message = body.get("message") or {}
        content = str(message.get("content") or "").strip()
        if not content:
            raise OllamaUnavailable("Ollama returned no final answer")

        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.I | re.S).strip()
        answer = ""
        try:
            decoded = json.loads(content)
            if isinstance(decoded, dict):
                answer = str(decoded.get("answer") or "").strip()
        except Exception:
            if require_json:
                raise OllamaUnavailable("Ollama did not follow the final-answer JSON schema")

        if not answer and not require_json:
            answer = cls._strip_thinking_blocks(content)

        if not answer:
            raise OllamaUnavailable("Ollama returned an empty final answer")
        if cls._looks_like_reasoning(answer):
            raise OllamaUnavailable("Ollama exposed internal reasoning instead of a final answer")
        if cls._looks_incomplete(answer):
            raise OllamaUnavailable("Ollama returned an incomplete final answer")
        return answer.strip()

    def _strip_thinking_blocks(value: str) -> str:
        text = re.sub(r"<think>.*?</think>", "", value, flags=re.I | re.S).strip()
        if "</think>" in text.lower():
            text = re.split(r"</think>", text, flags=re.I)[-1].strip()
        final_match = re.search(
            r"(?:^|\n)(?:final answer|answer)\s*:\s*(.+)$",
            text,
            flags=re.I | re.S,
        )
        return final_match.group(1).strip() if final_match else text

    def _looks_like_reasoning(value: str) -> bool:
        text = str(value or "").strip().lower()
        return any(re.search(pattern, text, flags=re.I | re.S) for pattern in _REASONING_PATTERNS)

    def _looks_incomplete(value: str) -> bool:
        text = str(value or "").rstrip()
        if len(text) < 2:
            return True
        trailing = (
            ":",
            "-",
            "•",
            ",",
            " and",
            " or",
            " but",
            " because",
            " the",
            " a",
        )
        return any(text.lower().endswith(suffix) for suffix in trailing)

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
        requested_model = str(model or "").strip()
        cloud_requested = bool(
            self.cloud_enabled
            and self.cloud_model
            and requested_model.lower() == self.cloud_model.lower()
        )

        if not cloud_requested:
            body = await self._final_answer_chat(
                model=requested_model,
                messages=messages,
                tools=tools,
                timeout_seconds=timeout_seconds,
                num_ctx=num_ctx,
                num_predict=num_predict,
                temperature=temperature,
            )
            result = dict(body)
            result["_homebrain_model_used"] = requested_model
            result["_homebrain_provider"] = self._http.last_provider("Local Ollama")
            _CHAT_MODEL_USED.set(requested_model)
            _CHAT_PROVIDER_USED.set(self._http.last_provider("Local Ollama"))
            return result

        cloud_error: Exception | None = None
        if self._cloud_present_hint is not False:
            cloud_timeout = min(
                self.cloud_timeout_seconds,
                max(8.0, float(timeout_seconds)),
            )
            try:
                body = await self._final_answer_chat(
                    model=requested_model,
                    messages=messages,
                    tools=tools,
                    timeout_seconds=cloud_timeout,
                    num_ctx=num_ctx,
                    num_predict=num_predict,
                    temperature=temperature,
                )
                provider = self._http.last_provider("Ollama Cloud")
                result = dict(body)
                result["_homebrain_model_used"] = requested_model
                result["_homebrain_provider"] = provider
                _CHAT_MODEL_USED.set(requested_model)
                _CHAT_PROVIDER_USED.set(provider)
                return result
            except Exception as exc:
                cloud_error = exc
        else:
            cloud_error = OllamaUnavailable(
                f"Ollama Cloud model {requested_model} is unavailable"
            )

        if (
            not self.cloud_fallback_local
            or not self.local_fallback_model
            or self.local_fallback_model.lower() == requested_model.lower()
        ):
            assert cloud_error is not None
            raise cloud_error

        body = await self._final_answer_chat(
            model=self.local_fallback_model,
            messages=messages,
            tools=tools,
            timeout_seconds=max(8.0, float(timeout_seconds)),
            num_ctx=num_ctx,
            num_predict=num_predict,
            temperature=temperature,
        )
        cloud_error_text = str(cloud_error) or cloud_error.__class__.__name__
        result = dict(body)
        result["_homebrain_model_used"] = self.local_fallback_model
        result["_homebrain_provider"] = "Local Ollama fallback"
        result["_homebrain_cloud_error"] = cloud_error_text
        _CHAT_MODEL_USED.set(self.local_fallback_model)
        _CHAT_PROVIDER_USED.set("Local Ollama fallback")
        _CHAT_CLOUD_ERROR.set(cloud_error_text)
        return result

    def _preferred_family_model(self, installed_models: list[str]) -> str:
        local_target = self.local_fallback_model or self.model
        response_family = local_target.split(":", 1)[0].lower()
        candidates = [
            name
            for name in installed_models
            if name
            and name.split(":", 1)[0].lower() == response_family
            and not name.lower().endswith("-cloud")
            and not any(term in name.lower() for term in ("embed", "nomic", "bge"))
        ]
        if not candidates:
            return local_target

        def model_size(name: str) -> float:
            match = re.search(r"(?<!\d)(\d+(?:\.\d+)?)b(?:\b|$)", name.lower())
            return float(match.group(1)) if match else 999.0

        def preference_key(name: str) -> tuple[float, int, float, str]:
            size = model_size(name)
            distance = abs(size - _TARGET_LOCAL_MODEL_BILLIONS)
            below_target = 1 if size < _TARGET_LOCAL_MODEL_BILLIONS else 0
            return distance, below_target, size, name.lower()

        candidates.sort(key=preference_key)
        return candidates[0]

    def _select_compact_tools(self, query: str, tools: list[MCPTool]) -> list[MCPTool]:
        unique: dict[str, MCPTool] = {}
        for tool in tools:
            name = str(getattr(tool, "name", "") or "").strip()
            if name:
                unique.setdefault(name, tool)

        def priority(tool: MCPTool) -> tuple[int, str]:
            name = str(tool.name)
            if name == _TARGETED_DEVICE_SEARCH:
                return -1, name
            if name in _DISCOVERY_TOOLS:
                return 0, name
            if name.startswith("hub_read_"):
                return 1, name
            if name.startswith("hub_manage_"):
                return 2, name
            if name.startswith("hub_"):
                return 3, name
            return 4, name

        ordered = sorted(unique.values(), key=priority)
        return ordered[: self.unified_tool_limit]

    def _planner_prompt(self) -> str:
        return (
            super()._planner_prompt()
            + "\n\nUnified-agent rules: when the user names or describes a particular "
            "physical device, call homebrain_search_devices first with only the current "
            "request's natural description. Use hub_read_devices afterwards when more live "
            "detail is required. When the user asks broadly to list, find or show devices "
            "without a distinguishing name, room or capability, call hub_list_devices rather "
            "than hub_read_devices. Do not reuse an entity from conversation history unless "
            "the current request explicitly refers to it. Do not use hub_search_tools to find "
            "physical devices. Tool-catalogue discovery is never authoritative home data. ""discovery is never the final step for a live-home question. After discovery, ""call hub_list_devices, hub_read_devices, homebrain_search_devices, or another ""authoritative MCP tool before producing the final answer."
        )

    def _is_broad_device_inventory_request(self, query: str) -> bool:
        words = _normalise_words(query)
        if not words or not any(word in {"device", "devices", "inventory"} for word in words):
            return False
        distinguishing = [word for word in words if word not in _GENERIC_DEVICE_QUERY_WORDS]
        return not distinguishing

    @staticmethod
    def _targeted_device_lookup(query: str) -> str | None:
        """Return the requested device description for an explicit lookup request."""

        match = _TARGETED_DEVICE_LOOKUP.fullmatch(str(query or "").strip())
        if not match:
            return None
        requested = " ".join(match.group(1).strip(" .!?").split())
        requested = re.sub(
            r"^(?:the\s+)?(?:device\s+)?",
            "",
            requested,
            flags=re.IGNORECASE,
        ).strip()
        requested = re.sub(
            r"\s+device$",
            "",
            requested,
            flags=re.IGNORECASE,
        ).strip()
        if not requested:
            return None
        words = _normalise_words(requested)
        if not words or all(word in _GENERIC_DEVICE_QUERY_WORDS for word in words):
            return None
        return requested

    async def _execute_tool_call(
        self,
        name: str,
        arguments: dict[str, Any],
        query: str,
    ) -> tuple[dict[str, Any], str]:
        """Repair a planner inventory call when the user requested one device.

        Small planning models occasionally choose ``hub_list_devices`` for requests such
        as "find front door". That tool is the authoritative inventory source but does not
        perform entity resolution. Redirect the call through HomeBrain's structured search
        broker before synthesis, keeping the model in the same multi-step agent loop.
        """

        requested = self._targeted_device_lookup(query)
        if name == "hub_list_devices" and requested:
            return await super()._execute_tool_call(
                _TARGETED_DEVICE_SEARCH,
                {"query": requested, "limit": 8},
                query,
            )
        return await super()._execute_tool_call(name, arguments, query)

    @staticmethod
    def _should_recover_with_inventory(error: Exception | str) -> bool:
        text = str(error or "").lower()
        return any(
            marker in text
            for marker in (
                "without authoritative home data",
                "did not execute an mcp tool for a live-home question",
                "tool request that could not be parsed",
            )
        )

    async def answer_with_planner(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        safe_history = history or []
        if self._is_broad_device_inventory_request(query):
            return await self._answer_from_device_inventory(query, safe_history)
        try:
            return await ClaudeStyleOllamaAgent.answer(self, query, safe_history)
        except OllamaUnavailable as exc:
            if not self._should_recover_with_inventory(exc):
                raise
            return await self._answer_from_targeted_device_search(query, safe_history, exc)

    async def _answer_from_device_inventory(
        self,
        query: str,
        history: list[dict[str, str]],
    ) -> dict[str, Any]:
        started = time.perf_counter()
        result = await self.client.call_tool("hub_list_devices", {})
        if result.is_error:
            raise OllamaUnavailable(f"Device inventory failed: {result.text}")

        rows = _device_rows(result.data)
        room_counts: Counter[str] = Counter()
        devices: list[dict[str, Any]] = []
        for item in rows[:160]:
            room = _room_name(item) or "No room assigned"
            room_counts[room] += 1
            devices.append(
                {
                    "id": _device_id(item),
                    "label": _label(item),
                    "room": room,
                    "capabilities": item.get("capabilities") or [],
                    "currentStates": _attributes(item),
                    "disabled": bool(item.get("disabled") is True),
                }
            )

        payload = {
            "device_count": len(rows),
            "room_counts": dict(sorted(room_counts.items())),
            "devices": devices,
        }
        tool_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
        planner_messages = [
            {"role": "tool", "tool_name": "hub_list_devices", "content": tool_text}
        ]
        body = await self._chat(
            model=self.model,
            messages=self._synthesis_messages(
                query=query,
                history=history,
                planner_messages=planner_messages,
            ),
            tools=None,
            timeout_seconds=self.response_timeout_seconds,
            num_ctx=self.num_ctx,
            num_predict=self.num_predict,
            temperature=0.15,
        )
        content = str((body.get("message") or {}).get("content") or "").strip()
        if not content:
            content = f"I found {len(rows)} selected Hubitat devices."
        elapsed = round((time.perf_counter() - started) * 1000)
        return {
            "success": True,
            "route": "ollama+mcp",
            "intent": "device-inventory",
            "message": content,
            "model": self.model,
            "tools_used": [
                {
                    "name": "hub_list_devices",
                    "arguments": {},
                    "success": True,
                    "preview": tool_text[:700],
                    "evidence": {"device_count": len(rows)},
                }
            ],
            "selected_tools": ["hub_list_devices"],
            "device_count": len(rows),
            "elapsed_ms": elapsed,
        }

    async def _answer_from_targeted_device_search(
        self,
        query: str,
        history: list[dict[str, str]],
        planner_error: Exception,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        requested = self._targeted_device_lookup(query) or query
        result = await self.client.call_tool(
            _TARGETED_DEVICE_SEARCH,
            {"query": requested, "limit": 8},
        )
        if result.is_error:
            raise OllamaUnavailable(
                f"Planner ended without data and targeted device search failed: {result.text}"
            ) from planner_error

        tool_text = self._compact_tool_result(result)
        planner_messages: list[dict[str, Any]] = [
            {
                "role": "tool",
                "tool_name": _TARGETED_DEVICE_SEARCH,
                "content": tool_text,
            }
        ]
        body = await self._chat(
            model=self.model,
            messages=self._synthesis_messages(
                query=query,
                history=history,
                planner_messages=planner_messages,
            ),
            tools=None,
            timeout_seconds=self.response_timeout_seconds,
            num_ctx=self.num_ctx,
            num_predict=self.num_predict,
            temperature=0.15,
        )
        content = str((body.get("message") or {}).get("content") or "").strip()
        if not content:
            raise OllamaUnavailable("Targeted device recovery returned no user-facing answer")

        elapsed = round((time.perf_counter() - started) * 1000)
        evidence = self._tool_evidence(result.data)
        return {
            "success": True,
            "route": "ollama+mcp",
            "intent": "unified-targeted-device-recovery",
            "message": content,
            "model": self.model,
            "planner_model": self._last_agent_status.get("planner_model"),
            "tools_used": [
                {
                    "name": _TARGETED_DEVICE_SEARCH,
                    "arguments": {"query": requested, "limit": 8},
                    "success": True,
                    "preview": tool_text[:700],
                    **({"evidence": evidence} if evidence else {}),
                }
            ],
            "selected_tools": [_TARGETED_DEVICE_SEARCH],
            "planner_error": str(planner_error),
            "authoritative_recovery": True,
            "targeted_device_search": True,
            "elapsed_ms": elapsed,
        }


__all__ = ["UnifiedAdaptiveMCPAgent"]
