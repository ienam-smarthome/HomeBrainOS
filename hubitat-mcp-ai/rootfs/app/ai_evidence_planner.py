from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import request_tracing
from control_agent_intent import is_control_candidate
from device_health_fast_route import is_device_health_query
from fallback_router import _device_id, _label, _normalise
from home_priority_insight import is_home_priority_query
from presenter import display_payload, first_mapping, safe_debug
from routing_policy import RouteDecision, classify_query
from semantic_metric_comparison import _SPECS, format_measurement


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]

_ALLOWED_KINDS = {
    "home_snapshot",
    "device_health",
    "measurements",
    "hub_health",
    "inventory",
    "recent_events",
    "weather",
    "light_usage",
}
_ALLOWED_METRICS = set(_SPECS)
_REASONING_TERMS = (
    "why",
    "explain",
    "analyse",
    "analyze",
    "diagnose",
    "issue",
    "problem",
    "important",
    "unusual",
    "wrong",
    "waste",
    "wasting",
    "improve",
    "recommend",
    "suggest",
    "should",
    "could",
    "needs attention",
    "need attention",
    "pattern",
    "correlate",
    "relationship",
    "most useful",
)
_HOME_DOMAIN_TERMS = (
    "home",
    "house",
    "hubitat",
    "device",
    "light",
    "lamp",
    "switch",
    "socket",
    "plug",
    "room",
    "battery",
    "power",
    "energy",
    "temperature",
    "humidity",
    "sensor",
    "motion",
    "presence",
    "door",
    "window",
    "fan",
    "heating",
    "thermostat",
    "trv",
    "robot",
    "roborock",
    "washing",
    "fridge",
    "freezer",
    "weather",
)
_AUTOMATION_WRITE_TERMS = (
    "create automation",
    "create rule",
    "modify rule",
    "change rule",
    "delete rule",
    "repair rule",
)

_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["analysis", "diagnosis", "recommendation", "explanation", "summary", "unsupported"],
        },
        "summary": {"type": "string", "maxLength": 240},
        "evidence": {
            "type": "array",
            "maxItems": 6,
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": sorted(_ALLOWED_KINDS)},
                    "metrics": {
                        "type": "array",
                        "maxItems": 6,
                        "items": {"type": "string", "enum": sorted(_ALLOWED_METRICS)},
                    },
                    "devices": {
                        "type": "array",
                        "maxItems": 6,
                        "items": {"type": "string", "maxLength": 120},
                    },
                    "hours_back": {"type": "integer", "minimum": 1, "maximum": 168},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 40},
                },
                "required": ["kind", "metrics", "devices", "hours_back", "limit"],
                "additionalProperties": False,
            },
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["intent", "summary", "evidence", "confidence"],
    "additionalProperties": False,
}

_REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["answer_ready", "need_more"]},
        "reason": {"type": "string", "maxLength": 240},
        "additional_evidence": _PLAN_SCHEMA["properties"]["evidence"],
    },
    "required": ["status", "reason", "additional_evidence"],
    "additionalProperties": False,
}


@dataclass(frozen=True, slots=True)
class EvidenceRequest:
    kind: str
    metrics: tuple[str, ...] = ()
    devices: tuple[str, ...] = ()
    hours_back: int = 24
    limit: int = 20

    def response_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "metrics": list(self.metrics),
            "devices": list(self.devices),
            "hours_back": self.hours_back,
            "limit": self.limit,
        }

    def key(self) -> str:
        return json.dumps(self.response_dict(), sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class EvidencePlan:
    intent: str
    summary: str
    evidence: tuple[EvidenceRequest, ...]
    confidence: float
    model: str | None = None
    provider: str | None = None

    def response_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "summary": self.summary,
            "evidence": [item.response_dict() for item in self.evidence],
            "confidence": self.confidence,
            "model": self.model,
            "provider": self.provider,
        }


def _normalised_query(query: str) -> str:
    return re.sub(r"\s+", " ", str(query or "").strip().lower()).strip(" .!?")


def is_ai_evidence_query(query: str) -> bool:
    q = _normalised_query(query)
    if not q or is_control_candidate(q) or is_device_health_query(q):
        return False
    if any(term in q for term in _AUTOMATION_WRITE_TERMS):
        return False

    decision = classify_query(q)
    if decision.route == "mcp-fast":
        return False
    if is_home_priority_query(q):
        return True

    home_domain = any(term in q for term in _HOME_DOMAIN_TERMS)
    reasoning = any(term in q for term in _REASONING_TERMS)
    if home_domain and reasoning:
        return True
    return bool(
        home_domain
        and decision.route in {"ollama-planner", "ollama-verified"}
        and q.startswith((
            "what", "which", "how", "is ", "are ", "tell me", "give me",
            "find", "locate", "where", "show", "check", "look up", "look for",
        ))
    )


def _bounded(value: Any, *, depth: int = 0, max_items: int = 30, max_text: int = 500) -> Any:
    if depth >= 5:
        return "[truncated]"
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= max_items:
                output["_truncated"] = len(value) - max_items
                break
            output[str(key)] = _bounded(item, depth=depth + 1, max_items=max_items, max_text=max_text)
        return output
    if isinstance(value, list):
        output = [
            _bounded(item, depth=depth + 1, max_items=max_items, max_text=max_text)
            for item in value[:max_items]
        ]
        if len(value) > max_items:
            output.append({"_truncated": len(value) - max_items})
        return output
    if isinstance(value, str) and len(value) > max_text:
        return value[:max_text] + "…"
    return value


def _history(request: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in list(getattr(request, "history", None) or [])[-4:]:
        if isinstance(item, dict):
            role = str(item.get("role") or "")
            content = str(item.get("content") or "")
        else:
            role = str(getattr(item, "role", "") or "")
            content = str(getattr(item, "content", "") or "")
        if role in {"user", "assistant"} and content:
            rows.append({"role": role, "content": content[:500]})
    return rows


class AIEvidencePlanner:
    """AI-led, evidence-bound read-only analysis with at most two evidence rounds."""

    def __init__(
        self,
        application: Any,
        device_index: Any,
        snapshot_service: Any,
        metric_executor: Any,
        *,
        enabled: bool = True,
        prefer_cloud: bool = True,
        max_rounds: int = 2,
        plan_timeout_seconds: float = 12.0,
        synthesis_timeout_seconds: float = 20.0,
        max_inventory_items: int = 120,
    ) -> None:
        self.application = application
        self.device_index = device_index
        self.snapshot_service = snapshot_service
        self.metric_executor = metric_executor
        self.enabled = bool(enabled)
        self.prefer_cloud = bool(prefer_cloud)
        self.max_rounds = max(1, min(2, int(max_rounds)))
        self.plan_timeout_seconds = max(4.0, min(30.0, float(plan_timeout_seconds)))
        self.synthesis_timeout_seconds = max(5.0, min(45.0, float(synthesis_timeout_seconds)))
        self.max_inventory_items = max(20, min(250, int(max_inventory_items)))

    def matches(self, query: str) -> bool:
        return self.enabled and is_ai_evidence_query(query)

    def _model_candidates(self) -> list[tuple[str, str, float]]:
        agent = self.application.ollama
        cloud = str(getattr(agent, "cloud_model", "") or "").strip()
        local = str(
            getattr(agent, "planner_model", "")
            or getattr(agent, "local_fallback_model", "")
            or getattr(agent, "model", "")
        ).strip()
        values: list[tuple[str, str, float]] = []
        seen: set[str] = set()

        def add(model: str, provider: str, timeout: float) -> None:
            key = model.lower()
            if model and key not in seen:
                seen.add(key)
                values.append((model, provider, timeout))

        if self.prefer_cloud and bool(getattr(agent, "cloud_enabled", False)):
            add(cloud, "Ollama Cloud evidence planner", self.plan_timeout_seconds)
        add(local, "Local Ollama evidence planner", min(self.plan_timeout_seconds, 6.0))
        if not self.prefer_cloud and bool(getattr(agent, "cloud_enabled", False)):
            add(cloud, "Ollama Cloud evidence planner", self.plan_timeout_seconds)
        return values

    async def _inventory(self) -> list[dict[str, Any]]:
        try:
            devices = list(await self.device_index.enriched_devices())
        except Exception:
            return []
        rows: list[dict[str, Any]] = []
        for item in devices[: self.max_inventory_items]:
            if not isinstance(item, dict) or item.get("disabled") is True:
                continue
            groups: list[str] = []
            try:
                groups = sorted(str(value) for value in self.device_index._groups(item))
            except Exception:
                pass
            rows.append(
                {
                    "label": _label(item),
                    "room": str(item.get("room") or item.get("roomName") or ""),
                    "groups": groups[:8],
                }
            )
        return rows

    async def _structured_chat(
        self,
        *,
        schema: dict[str, Any],
        system: str,
        user: str,
    ) -> tuple[dict[str, Any], str, str, list[dict[str, Any]]]:
        agent = self.application.ollama
        client = getattr(agent, "_http", None)
        post = getattr(client, "post", None)
        if not callable(post):
            raise RuntimeError("Ollama HTTP client is unavailable")

        attempts: list[dict[str, Any]] = []
        last_error: Exception | None = None
        for model, provider, timeout in self._model_candidates():
            try:
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "think": False,
                    "format": schema,
                    "keep_alive": str(getattr(agent, "keep_alive", "30m") or "30m"),
                    "options": {
                        "num_ctx": min(int(getattr(agent, "num_ctx", 2048)), 3072),
                        "num_predict": 500,
                        "temperature": 0,
                    },
                }
                response = await post(
                    f"{str(agent.base_url).rstrip('/')}/api/chat",
                    json=payload,
                    timeout=timeout,
                )
                response.raise_for_status()
                body = response.json()
                message = body.get("message") if isinstance(body, dict) else None
                content = str((message or {}).get("content") or "").strip()
                content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.I | re.S).strip()
                decoded = json.loads(content)
                actual_provider = provider
                reader = getattr(client, "last_provider", None)
                if callable(reader):
                    actual_provider = str(reader(provider) or provider)
                attempts.append({"model": model, "provider": actual_provider, "success": True})
                return decoded, model, actual_provider, attempts
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_error = exc
                attempts.append(
                    {
                        "model": model,
                        "provider": provider,
                        "success": False,
                        "error": str(exc).strip() or type(exc).__name__,
                    }
                )
        summary = "; ".join(
            f"{item['model']}: {item.get('error') or 'failed'}" for item in attempts
        )
        raise RuntimeError(summary or str(last_error) or "No evidence-planner model is available")

    @staticmethod
    def _validate_requests(raw: Any, *, max_items: int = 6) -> tuple[EvidenceRequest, ...]:
        if not isinstance(raw, list):
            return ()
        output: list[EvidenceRequest] = []
        seen: set[str] = set()
        for item in raw[:max_items]:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind") or "").strip().lower()
            if kind not in _ALLOWED_KINDS:
                continue
            metrics = tuple(
                value
                for value in dict.fromkeys(
                    str(value or "").strip().lower()
                    for value in list(item.get("metrics") or [])[:6]
                )
                if value in _ALLOWED_METRICS
            )
            devices = tuple(
                value
                for value in dict.fromkeys(
                    re.sub(r"\s+", " ", str(value or "").strip())
                    for value in list(item.get("devices") or [])[:6]
                )
                if value
            )
            hours_back = max(1, min(168, int(item.get("hours_back") or 24)))
            limit = max(1, min(40, int(item.get("limit") or 20)))
            if kind == "measurements" and not metrics:
                continue
            if kind == "recent_events" and not devices:
                continue
            request = EvidenceRequest(kind, metrics, devices, hours_back, limit)
            if request.key() in seen:
                continue
            seen.add(request.key())
            output.append(request)
        return tuple(output)

    def _validate_plan(
        self,
        raw: Any,
        *,
        model: str | None = None,
        provider: str | None = None,
    ) -> EvidencePlan | None:
        if not isinstance(raw, dict):
            return None
        intent = str(raw.get("intent") or "").strip().lower()
        if intent not in {"analysis", "diagnosis", "recommendation", "explanation", "summary", "unsupported"}:
            return None
        evidence = self._validate_requests(raw.get("evidence"))
        if intent != "unsupported" and not evidence:
            return None
        try:
            confidence = max(0.0, min(1.0, float(raw.get("confidence") or 0)))
        except Exception:
            confidence = 0.0
        return EvidencePlan(
            intent=intent,
            summary=str(raw.get("summary") or "").strip()[:240],
            evidence=evidence,
            confidence=confidence,
            model=model,
            provider=provider,
        )

    def _default_plan(self, query: str, *, reason: str = "") -> EvidencePlan:
        q = _normalised_query(query)
        requests: list[EvidenceRequest] = [
            EvidenceRequest("home_snapshot", limit=20),
            EvidenceRequest("device_health", limit=20),
        ]
        metrics: list[str] = []
        for metric, terms in {
            "power": ("power", "electric", "watt", "load", "waste"),
            "energy": ("energy", "kwh", "cost"),
            "temperature": ("temperature", "warm", "cold", "heat"),
            "humidity": ("humidity", "damp", "moist"),
            "battery": ("battery", "charge"),
            "illuminance": ("lux", "brightness", "dark"),
        }.items():
            if any(term in q for term in terms):
                metrics.append(metric)
        if metrics:
            requests.append(EvidenceRequest("measurements", tuple(metrics), limit=30))
        if "weather" in q or "outside" in q or "rain" in q:
            requests.append(EvidenceRequest("weather", limit=10))
        if "light" in q and any(term in q for term in ("today", "longest", "on time", "usage")):
            requests.append(EvidenceRequest("light_usage", limit=30))
        return EvidencePlan(
            intent="analysis",
            summary=("Safe deterministic evidence plan" + (f" after planner error: {reason}" if reason else ""))[:240],
            evidence=tuple(requests[:6]),
            confidence=0.45,
            model=None,
            provider=None,
        )

    async def plan(self, query: str, request: Any, inventory: list[dict[str, Any]]) -> tuple[EvidencePlan, list[dict[str, Any]], str | None]:
        context = _history(request)
        system = (
            "/no_think\n"
            "You are the read-only evidence planner for HomeBrain. Decide what authoritative "
            "Hubitat evidence Python must gather before answering. You may choose only the supplied "
            "evidence kinds. Never request a write, command, arbitrary MCP tool, device ID or invented "
            "state. Use home_snapshot for a broad current overview; device_health for offline/stale; "
            "measurements for live numeric power, energy, temperature, humidity, battery or illuminance; "
            "hub_health for hub warnings; inventory for capabilities/coverage; recent_events only for up "
            "to six exact selected-device labels; weather for the weather device; light_usage for today's "
            "calculated light-on history. Prefer the smallest sufficient plan. Return strict JSON only."
        )
        user = (
            f"Question: {query.strip()}\n"
            f"Recent conversation: {json.dumps(context, ensure_ascii=False, separators=(',', ':'))}\n"
            "Approved evidence catalogue: home_snapshot, device_health, measurements, hub_health, "
            "inventory, recent_events, weather, light_usage.\n"
            f"Selected-device catalogue: {json.dumps(inventory, ensure_ascii=False, separators=(',', ':'))}"
        )
        try:
            raw, model, provider, attempts = await self._structured_chat(
                schema=_PLAN_SCHEMA,
                system=system,
                user=user,
            )
            plan = self._validate_plan(raw, model=model, provider=provider)
            if plan is None or plan.intent == "unsupported":
                raise RuntimeError("Evidence planner returned unsupported or invalid plan")
            return plan, attempts, None
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            error = str(exc).strip() or type(exc).__name__
            return self._default_plan(query, reason=error), [], error

    async def _home_snapshot(self, request: EvidenceRequest) -> dict[str, Any]:
        errors: list[str] = []
        devices, diagnostics, hub_status = await self.snapshot_service._load_sources(
            force=False,
            coverage_errors=errors,
        )
        snapshot = self.snapshot_service._build_snapshot(devices, diagnostics, hub_status)
        return {
            "source": "home_snapshot",
            "success": int(snapshot.get("states_read") or 0) > 0,
            "coverage_errors": errors,
            "data": _bounded(
                {
                    "selected_devices": snapshot.get("selected_devices"),
                    "states_read": snapshot.get("states_read"),
                    "attention": list(snapshot.get("attention") or [])[: request.limit],
                    "open_contacts": list(snapshot.get("open_contacts") or [])[: request.limit],
                    "motion_active": list(snapshot.get("motion_active") or [])[: request.limit],
                    "lights_on": list(snapshot.get("lights_on") or [])[: request.limit],
                    "devices_on": list(snapshot.get("devices_on") or [])[: request.limit],
                    "heating": list(snapshot.get("heating") or [])[: request.limit],
                }
            ),
        }

    async def _device_health(self, request: EvidenceRequest) -> dict[str, Any]:
        method = getattr(self.application.fallback, "_device_health", None)
        if not callable(method):
            return {"source": "device_health", "success": False, "error": "Device-health collector unavailable"}
        answer = dict(await method())
        return {
            "source": "device_health",
            "success": bool(answer.get("success", True)),
            "data": _bounded(
                {
                    "offline_devices": list(answer.get("offline_devices") or [])[: request.limit],
                    "stale_telemetry": list(answer.get("stale_telemetry") or [])[: request.limit],
                    "quiet_timestamp_devices": list(answer.get("quiet_timestamp_devices") or [])[: request.limit],
                    "threshold_hours": answer.get("threshold_hours"),
                    "message": answer.get("message"),
                }
            ),
        }

    async def _hub_health(self, request: EvidenceRequest) -> dict[str, Any]:
        result = await self.application.mcp.call_tool("hub_get_info", {"includeHealthAlerts": True})
        return {
            "source": "hub_health",
            "success": not result.is_error,
            "error": result.text if result.is_error else None,
            "data": _bounded(first_mapping(result.data) if not result.is_error else {}),
        }

    async def _inventory_evidence(self, request: EvidenceRequest, inventory: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "source": "inventory",
            "success": bool(inventory),
            "data": {
                "count": len(inventory),
                "devices": inventory[: request.limit],
            },
        }

    async def _measurements(self, request: EvidenceRequest) -> dict[str, Any]:
        values: dict[str, Any] = {}
        errors: dict[str, str] = {}
        for metric in request.metrics:
            spec = _SPECS.get(metric)
            if spec is None:
                continue
            try:
                result = await self.metric_executor._fresh_capability_result(spec)
                rows = self.metric_executor.router._device_rows(result.data)
                readings = self.metric_executor._measurement_rows(rows, spec)
                readings.sort(key=lambda item: (-float(item.get("value") or 0), str(item.get("label") or "").lower()))
                values[metric] = [
                    {
                        "device": item.get("label"),
                        "room": item.get("room"),
                        "value": item.get("value"),
                        "formatted": format_measurement(spec, float(item.get("value") or 0)),
                        "aggregate": bool(item.get("aggregate")),
                        "attribute": item.get("source_attribute"),
                    }
                    for item in readings[: request.limit]
                ]
            except Exception as exc:
                errors[metric] = str(exc).strip() or type(exc).__name__
        return {
            "source": "measurements",
            "success": bool(values),
            "metrics": list(request.metrics),
            "errors": errors,
            "data": _bounded(values),
        }

    @staticmethod
    def _resolve_event_devices(
        requested: tuple[str, ...],
        raw_devices: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        by_label = {
            _normalise(_label(item)): item
            for item in raw_devices
            if isinstance(item, dict) and _label(item) and _device_id(item) is not None
        }
        resolved: list[dict[str, Any]] = []
        missing: list[str] = []
        for name in requested:
            match = by_label.get(_normalise(name))
            if match is None:
                missing.append(name)
            else:
                resolved.append(match)
        return resolved, missing

    async def _recent_events(
        self,
        request: EvidenceRequest,
        raw_devices: list[dict[str, Any]],
    ) -> dict[str, Any]:
        resolved, missing = self._resolve_event_devices(request.devices, raw_devices)
        semaphore = asyncio.Semaphore(3)

        async def read(item: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                desired = {"deviceId": _device_id(item), "hoursBack": request.hours_back}
                supported = getattr(self.application.mcp, "supported_arguments", None)
                args = await supported("hub_list_device_events", desired) if callable(supported) else desired
                result = await self.application.mcp.call_tool("hub_list_device_events", args)
                return {
                    "device": _label(item),
                    "success": not result.is_error,
                    "error": result.text if result.is_error else None,
                    "events": _bounded(result.data, max_items=request.limit),
                }

        rows = await asyncio.gather(*(read(item) for item in resolved)) if resolved else []
        return {
            "source": "recent_events",
            "success": bool(rows) and any(item.get("success") for item in rows),
            "hours_back": request.hours_back,
            "missing_devices": missing,
            "data": rows,
        }

    async def _weather(self, request: EvidenceRequest) -> dict[str, Any]:
        method = getattr(self.application.fallback, "_find_weather", None)
        if not callable(method):
            return {"source": "weather", "success": False, "error": "Weather collector unavailable"}
        answer = dict(await method())
        return {
            "source": "weather",
            "success": bool(answer.get("success")),
            "data": _bounded({"message": answer.get("message"), "intent": answer.get("intent")}),
        }

    async def _light_usage(self, request: EvidenceRequest) -> dict[str, Any]:
        method = getattr(self.application.fallback, "_light_usage_today", None)
        if not callable(method):
            return {"source": "light_usage", "success": False, "error": "Light-usage collector unavailable"}
        answer = dict(await method())
        return {
            "source": "light_usage",
            "success": bool(answer.get("success")),
            "data": _bounded(
                {
                    "message": answer.get("message"),
                    "combined_seconds": answer.get("combined_seconds"),
                    "usage": list(answer.get("usage") or [])[: request.limit],
                    "incomplete_logs": answer.get("incomplete_logs"),
                }
            ),
        }

    async def gather(
        self,
        requests: tuple[EvidenceRequest, ...],
        *,
        inventory: list[dict[str, Any]],
        raw_devices: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        async def one(request: EvidenceRequest) -> dict[str, Any]:
            try:
                if request.kind == "home_snapshot":
                    return await self._home_snapshot(request)
                if request.kind == "device_health":
                    return await self._device_health(request)
                if request.kind == "hub_health":
                    return await self._hub_health(request)
                if request.kind == "inventory":
                    return await self._inventory_evidence(request, inventory)
                if request.kind == "measurements":
                    return await self._measurements(request)
                if request.kind == "recent_events":
                    return await self._recent_events(request, raw_devices)
                if request.kind == "weather":
                    return await self._weather(request)
                if request.kind == "light_usage":
                    return await self._light_usage(request)
                return {"source": request.kind, "success": False, "error": "Unsupported evidence kind"}
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                return {
                    "source": request.kind,
                    "success": False,
                    "error": str(exc).strip() or type(exc).__name__,
                }

        return list(await asyncio.gather(*(one(request) for request in requests)))

    async def review(
        self,
        *,
        query: str,
        plan: EvidencePlan,
        evidence: list[dict[str, Any]],
    ) -> tuple[tuple[EvidenceRequest, ...], dict[str, Any]]:
        if self.max_rounds < 2:
            return (), {"status": "disabled"}
        system = (
            "/no_think\n"
            "You are HomeBrain's evidence sufficiency reviewer. Inspect the verified first-round "
            "evidence and decide whether the user can be answered honestly. Request only a small "
            "additional set from the approved read-only evidence catalogue. Do not repeat existing "
            "requests, do not request writes or arbitrary tools, and return strict JSON only."
        )
        user = (
            f"Question: {query.strip()}\n"
            f"Initial plan: {json.dumps(plan.response_dict(), ensure_ascii=False, separators=(',', ':'))}\n"
            f"First-round evidence: {json.dumps(_bounded(evidence), ensure_ascii=False, separators=(',', ':'))}"
        )
        try:
            raw, model, provider, attempts = await self._structured_chat(
                schema=_REVIEW_SCHEMA,
                system=system,
                user=user,
            )
            status = str(raw.get("status") or "").strip().lower() if isinstance(raw, dict) else ""
            additional = self._validate_requests(raw.get("additional_evidence"), max_items=3) if isinstance(raw, dict) else ()
            existing = {item.key() for item in plan.evidence}
            additional = tuple(item for item in additional if item.key() not in existing)
            if status != "need_more":
                additional = ()
            return additional, {
                "status": status or "invalid",
                "reason": str(raw.get("reason") or "")[:240] if isinstance(raw, dict) else "",
                "model": model,
                "provider": provider,
                "attempts": attempts,
                "additional_evidence": [item.response_dict() for item in additional],
            }
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return (), {
                "status": "review_failed",
                "error": str(exc).strip() or type(exc).__name__,
            }

    @staticmethod
    def _deterministic_answer(query: str, evidence: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for item in evidence:
            source = str(item.get("source") or "evidence")
            if not item.get("success"):
                if item.get("error"):
                    lines.append(f"{source.replace('_', ' ').title()} was unavailable: {item['error']}.")
                continue
            data = item.get("data")
            if source == "home_snapshot" and isinstance(data, dict):
                attention = list(data.get("attention") or [])
                contacts = list(data.get("open_contacts") or [])
                lights = list(data.get("lights_on") or [])
                lines.append(
                    f"The live snapshot found {len(attention)} attention item(s), {len(contacts)} open contact(s), "
                    f"and {len(lights)} light(s) on."
                )
            elif source == "device_health" and isinstance(data, dict):
                lines.append(
                    f"Device health found {len(data.get('offline_devices') or [])} offline and "
                    f"{len(data.get('stale_telemetry') or [])} stale-telemetry device(s)."
                )
            elif source == "measurements" and isinstance(data, dict):
                for metric, rows in data.items():
                    rows = list(rows or [])
                    if rows:
                        first = rows[0]
                        lines.append(
                            f"Highest returned {metric}: {first.get('device')} at {first.get('formatted')}."
                        )
            elif source in {"weather", "light_usage"} and isinstance(data, dict) and data.get("message"):
                lines.append(str(data["message"]))
            elif source == "recent_events" and isinstance(data, list):
                lines.append(f"Recent event history was read for {len(data)} device(s).")
            elif source == "hub_health" and isinstance(data, dict):
                alerts = data.get("healthAlerts")
                if alerts:
                    lines.append("Hub health alerts were returned and are included in Technical details.")
        if not lines:
            return (
                "HomeBrain could not obtain enough authoritative evidence to answer this safely. "
                "No estimate or invented device state was used."
            )
        return " ".join(lines[:6])

    async def synthesise(
        self,
        *,
        query: str,
        plan: EvidencePlan,
        evidence_rounds: list[list[dict[str, Any]]],
    ) -> tuple[str, str | None, str | None, str | None]:
        evidence = [item for round_items in evidence_rounds for item in round_items]
        deterministic = self._deterministic_answer(query, evidence)
        agent = self.application.ollama
        model = plan.model or str(getattr(agent, "cloud_model", "") or getattr(agent, "model", "")).strip()
        if not model:
            return deterministic, None, None, "No synthesis model is configured"
        messages = [
            {
                "role": "system",
                "content": (
                    "You are HomeBrain, an evidence-bound smart-home assistant. Answer the user's "
                    "question directly using only the verified evidence supplied. Distinguish facts from "
                    "inferences and recommendations. Never invent a device, state, event, cause or numeric "
                    "value. Mention evidence gaps that materially affect the conclusion. Use exact device "
                    "names. Do not claim any action was taken. Keep the answer concise but useful."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question: {query.strip()}\n"
                    f"AI evidence plan: {json.dumps(plan.response_dict(), ensure_ascii=False, separators=(',', ':'))}\n"
                    f"Verified evidence rounds: {json.dumps(_bounded(evidence_rounds), ensure_ascii=False, separators=(',', ':'))}\n"
                    f"Deterministic fallback summary: {deterministic}"
                ),
            },
        ]
        try:
            body = await agent._chat(
                model=model,
                messages=messages,
                tools=None,
                timeout_seconds=self.synthesis_timeout_seconds,
                num_ctx=min(int(getattr(agent, "num_ctx", 2048)), 4096),
                num_predict=350,
                temperature=0.1,
            )
            content = str((body.get("message") or {}).get("content") or "").strip()
            if not content:
                raise RuntimeError("Ollama returned an empty evidence-grounded answer")
            actual_model = str(body.get("_homebrain_model_used") or model).strip()
            provider = str(
                body.get("_homebrain_provider")
                or getattr(getattr(agent, "_http", None), "last_provider", lambda *_: None)()
                or plan.provider
                or "Ollama"
            ).strip()
            return content, actual_model, provider, None
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return deterministic, None, None, str(exc).strip() or type(exc).__name__

    async def answer(self, request: Any) -> dict[str, Any]:
        started = time.perf_counter()
        query = str(getattr(request, "query", "") or "").strip()
        inventory = await self._inventory()
        try:
            raw_devices = list(await self.device_index.enriched_devices())
        except Exception:
            raw_devices = []

        plan, planner_attempts, planner_error = await self.plan(query, request, inventory)
        first_round = await self.gather(plan.evidence, inventory=inventory, raw_devices=raw_devices)
        evidence_rounds = [first_round]
        additional, review = await self.review(query=query, plan=plan, evidence=first_round)
        if additional:
            evidence_rounds.append(
                await self.gather(additional, inventory=inventory, raw_devices=raw_devices)
            )

        message, model, provider, synthesis_error = await self.synthesise(
            query=query,
            plan=plan,
            evidence_rounds=evidence_rounds,
        )
        flat = [item for round_items in evidence_rounds for item in round_items]
        successful = [item for item in flat if item.get("success")]
        failed = [item for item in flat if not item.get("success")]
        source_names = [str(item.get("source") or "unknown") for item in successful]
        elapsed = round((time.perf_counter() - started) * 1000)

        items = [
            {
                "icon": "✅" if item.get("success") else "⚠️",
                "title": str(item.get("source") or "Evidence").replace("_", " ").title(),
                "value": "Collected" if item.get("success") else "Unavailable",
                "subtitle": str(item.get("error") or "Verified read-only evidence"),
                "tone": None if item.get("success") else "warning",
                "group": f"Evidence round {round_index + 1}",
            }
            for round_index, round_items in enumerate(evidence_rounds)
            for item in round_items
        ]
        display = display_payload(
            "ai-evidence-planner",
            "AI evidence answer",
            subtitle=(
                f"{len(evidence_rounds)} evidence round{'s' if len(evidence_rounds) != 1 else ''} · "
                f"{len(successful)} source{'s' if len(successful) != 1 else ''} collected"
            ),
            metrics=[
                {"label": "Evidence rounds", "value": str(len(evidence_rounds)), "icon": "🔎"},
                {"label": "Sources used", "value": str(len(successful)), "icon": "📚"},
                {"label": "Unavailable", "value": str(len(failed)), "icon": "⚠️"},
            ],
            items=items,
            note=(
                "AI selected only approved read-only evidence categories. Python gathered the live Hubitat "
                "data and retained control of every MCP call, calculation, safety check and write path."
            ),
        )
        display["summary"] = message

        answer: dict[str, Any] = {
            "success": bool(successful),
            "route": "ollama+evidence-planner" if model else "mcp-evidence-planner",
            "intent": "ai-evidence-planner",
            "message": message,
            "display": display,
            "evidence_plan": plan.response_dict(),
            "evidence_rounds": evidence_rounds,
            "evidence_sources": source_names,
            "planner_attempts": planner_attempts,
            "planner_error": planner_error,
            "review": review,
            "synthesis_error": synthesis_error,
            "model": model,
            "ai_provider": provider,
            "answered_by": (
                "AI evidence planning + deterministic Hubitat reads + evidence-grounded AI synthesis"
                if model
                else "Deterministic Hubitat evidence fallback"
            ),
            "elapsed_ms": elapsed,
            "technical": safe_debug(
                {
                    "query": query,
                    "plan": plan.response_dict(),
                    "planner_attempts": planner_attempts,
                    "planner_error": planner_error,
                    "review": review,
                    "evidence_rounds": evidence_rounds,
                    "synthesis_error": synthesis_error,
                    "model": model,
                    "ai_provider": provider,
                    "write_tools_available_to_model": False,
                    "maximum_evidence_rounds": self.max_rounds,
                }
            ),
        }
        if not model:
            answer.pop("model", None)
            answer.pop("ai_provider", None)
        return answer


def install_ai_evidence_planner(
    application: Any,
    device_index: Any,
    snapshot_service: Any,
    metric_executor: Any,
    *,
    enabled: bool = True,
    prefer_cloud: bool = True,
    max_rounds: int = 2,
    plan_timeout_seconds: float = 12.0,
    synthesis_timeout_seconds: float = 20.0,
    max_inventory_items: int = 120,
) -> AIEvidencePlanner:
    original_ask: AskHandler = application.ask
    original_classifier = request_tracing.classify_query
    service = AIEvidencePlanner(
        application,
        device_index,
        snapshot_service,
        metric_executor,
        enabled=enabled,
        prefer_cloud=prefer_cloud,
        max_rounds=max_rounds,
        plan_timeout_seconds=plan_timeout_seconds,
        synthesis_timeout_seconds=synthesis_timeout_seconds,
        max_inventory_items=max_inventory_items,
    )

    def classify_with_evidence_planner(query: str) -> RouteDecision:
        if service.matches(query):
            return RouteDecision(
                "ai-evidence",
                (
                    "AI selects from an approved read-only evidence catalogue; Python gathers and "
                    "calculates authoritative Hubitat evidence before grounded synthesis"
                ),
            )
        return original_classifier(query)

    request_tracing.classify_query = classify_with_evidence_planner

    async def ask_with_evidence_planner(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "").strip()
        if not service.matches(query):
            return await original_ask(request)
        answer = dict(await service.answer(request))
        answer.setdefault("version", application.VERSION)
        return answer

    application.ask = ask_with_evidence_planner
    application.ai_evidence_planner = service
    return service


__all__ = [
    "AIEvidencePlanner",
    "EvidencePlan",
    "EvidenceRequest",
    "install_ai_evidence_planner",
    "is_ai_evidence_query",
]
