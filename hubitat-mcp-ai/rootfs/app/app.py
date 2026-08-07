from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any, Awaitable

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, model_validator

from api_response_builder import build_agent_response
from automation_ideas_service import suggest_new_automations
from automation_status_service import AutomationStatusService
from device_state_summary import (
    active_non_light_switches,
    active_room_summary,
    device_attributes,
    is_light_device,
    room_name,
)
from homebrain_agent import UnifiedMCPAgent
from mcp_client import HubitatMCPClient
from webui import render_page

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HomeBrainOS.App")

OPTIONS_PATH = Path(os.getenv("CONFIG_PATH", "/data/options.json"))
VERSION_PATH = Path("/app/.homebrain-build-version")
VERSION = VERSION_PATH.read_text(encoding="utf-8").strip() if VERSION_PATH.exists() else "dev"


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def load_options() -> dict[str, Any]:
    options: dict[str, Any] = {
        "hubitat_mcp_url": "",
        "hubitat_mcp_token": "",
        "ollama_direct_cloud_enabled": True,
        "ollama_direct_cloud_base_url": "https://ollama.com",
        "ollama_direct_cloud_api_key": "",
        "ollama_direct_cloud_model": "gemma4:31b-cloud",
        "ollama_cloud_model": "gemma4:31b-cloud",
        "ollama_local_enabled": False,
        "ollama_local_base_url": "http://localhost:11434",
        "ollama_local_model": "",
        "ollama_local_timeout_seconds": 12,
        "ollama_local_connect_timeout_seconds": 3,
        "ollama_local_keep_alive_seconds": 120,
        "ollama_agent_timeout_seconds": 60,
        "stream_idle_timeout_seconds": 20,
        "mcp_timeout_seconds": 25,
        "mcp_device_cache_seconds": 12,
        "mcp_retry_attempts": 3,
        "mcp_retry_backoff_seconds": 0.25,
        "confirmation_ttl_seconds": 120,
        "unified_mcp_tool_limit": 48,
        "unified_mcp_max_tool_rounds": 9,
        "max_tool_result_chars": 24000,
        "require_sensitive_confirmation": True,
        "web_title": "Hubitat MCP AI",
    }
    if OPTIONS_PATH.exists():
        try:
            loaded = json.loads(OPTIONS_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                options.update(loaded)
        except Exception as exc:
            logger.warning("Could not load %s: %s", OPTIONS_PATH, exc)
    for key in tuple(options):
        env_name = f"HMCP_{key.upper()}"
        if env_name in os.environ:
            options[key] = os.environ[env_name]
    return options


OPTIONS = load_options()
mcp = HubitatMCPClient(
    endpoint_url=str(OPTIONS.get("hubitat_mcp_url") or ""),
    access_token=str(OPTIONS.get("hubitat_mcp_token") or ""),
    timeout_seconds=float(OPTIONS.get("mcp_timeout_seconds") or 25),
    device_cache_seconds=float(OPTIONS.get("mcp_device_cache_seconds") or 12),
    retry_attempts=int(OPTIONS.get("mcp_retry_attempts") or 3),
    retry_backoff_seconds=float(
        OPTIONS.get("mcp_retry_backoff_seconds") or 0.25
    ),
)
automation_status = AutomationStatusService(mcp)
agent = UnifiedMCPAgent(
    mcp_client=mcp,
    api_key=str(OPTIONS.get("ollama_direct_cloud_api_key") or ""),
    model_name=str(
        OPTIONS.get("ollama_direct_cloud_model")
        or OPTIONS.get("ollama_cloud_model")
        or "gemma4:31b-cloud"
    ),
    base_url=str(OPTIONS.get("ollama_direct_cloud_base_url") or "https://ollama.com"),
    local_base_url=(
        str(OPTIONS.get("ollama_local_base_url") or "")
        if _bool(OPTIONS.get("ollama_local_enabled"), False)
        else ""
    ),
    local_model_name=(
        str(OPTIONS.get("ollama_local_model") or "")
        if _bool(OPTIONS.get("ollama_local_enabled"), False)
        else ""
    ),
    local_timeout_seconds=float(OPTIONS.get("ollama_local_timeout_seconds") or 12),
    local_connect_timeout_seconds=float(
        OPTIONS.get("ollama_local_connect_timeout_seconds") or 3
    ),
    local_keep_alive_seconds=float(
        OPTIONS.get("ollama_local_keep_alive_seconds") or 120
    ),
    timeout_seconds=float(OPTIONS.get("ollama_agent_timeout_seconds") or 60),
    stream_idle_timeout_seconds=float(
        OPTIONS.get("stream_idle_timeout_seconds") or 20
    ),
    tool_limit=int(OPTIONS.get("unified_mcp_tool_limit") or 48),
    max_tool_rounds=int(OPTIONS.get("unified_mcp_max_tool_rounds") or 9),
    max_tool_result_chars=int(OPTIONS.get("max_tool_result_chars") or 24000),
    require_sensitive_confirmation=_bool(
        OPTIONS.get("require_sensitive_confirmation"), True
    ),
    confirmation_ttl_seconds=float(OPTIONS.get("confirmation_ttl_seconds") or 120),
)


class RequestCoordinator:
    """Own in-flight agent tasks so supersede and disconnect cancel backend work."""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._lock = asyncio.Lock()

    async def run(
        self,
        key: str,
        operation: Awaitable[Any],
        *,
        connection: Request | None = None,
    ) -> Any:
        task = asyncio.create_task(operation, name=f"homebrain-request:{key}")
        async with self._lock:
            previous = self._tasks.get(key)
            self._tasks[key] = task

        if previous is not None and previous is not task and not previous.done():
            previous.cancel("superseded by a newer request")
            with suppress(asyncio.CancelledError):
                await previous

        try:
            while True:
                done, _ = await asyncio.wait({task}, timeout=0.1)
                if task in done:
                    return task.result()
                if connection is not None and await connection.is_disconnected():
                    task.cancel("client disconnected")
                    with suppress(asyncio.CancelledError):
                        await task
                    raise HTTPException(status_code=499, detail="Client disconnected")
        except asyncio.CancelledError:
            if not task.done():
                task.cancel("request handler cancelled")
                with suppress(asyncio.CancelledError):
                    await task
            raise
        finally:
            async with self._lock:
                if self._tasks.get(key) is task:
                    self._tasks.pop(key, None)

    async def close(self) -> None:
        async with self._lock:
            tasks = list(self._tasks.values())
            self._tasks.clear()
        for task in tasks:
            if not task.done():
                task.cancel("application shutdown")
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task


request_coordinator = RequestCoordinator()


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        yield
    finally:
        await request_coordinator.close()
        await agent.close()
        await mcp.close()


app = FastAPI(
    title=str(OPTIONS.get("web_title") or "Hubitat MCP AI"),
    version=VERSION,
    lifespan=lifespan,
)


class HistoryItem(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    prompt: str | None = Field(default=None, max_length=2000)
    query: str | None = Field(default=None, max_length=2000)
    history: list[HistoryItem] = Field(default_factory=list)
    session_id: str = Field(default="default", min_length=1, max_length=160)
    request_id: str | None = Field(default=None, min_length=1, max_length=160)

    @model_validator(mode="after")
    def require_message(self) -> "ChatRequest":
        value = (self.prompt or self.query or "").strip()
        if not value:
            raise ValueError("Prompt required")
        return self

    @property
    def message(self) -> str:
        return (self.prompt or self.query or "").strip()

    @property
    def coordination_key(self) -> str:
        return self.session_id


async def _creative_automation_recommendation() -> Any:
    """Advisory automations request that specifically wants NEW ideas.

    Runs the same deterministic gap-analysis snapshot first (so the
    grounded fallback is always available), then asks the model to
    synthesize creative, themed suggestions from that same real data. If
    the model call fails or produces nothing, the deterministic message is
    returned completely unchanged -- this can only ever add to the
    response, never break it.
    """

    outcome = await automation_status.snapshot(advisory=True)
    suggestion = await suggest_new_automations(
        agent.transport.chat,
        outcome.automation_items,
        outcome.devices,
    )
    if suggestion:
        outcome.message = (
            suggestion
            + "\n\n---\nGrounded detail from your existing automations:\n"
            + outcome.message
        )
    return outcome


async def _answer_result(request: ChatRequest, connection: Request | None = None) -> Any:
    try:
        operation: Awaitable[Any]
        if automation_status.matches_request(request.message):
            if automation_status.is_advisory_request(
                request.message
            ) and automation_status.wants_new_automation_ideas(request.message):
                operation = _creative_automation_recommendation()
            else:
                operation = automation_status.snapshot(
                    advisory=automation_status.is_advisory_request(request.message)
                )
        else:
            if not _bool(OPTIONS.get("ollama_direct_cloud_enabled"), True):
                raise HTTPException(status_code=503, detail="Ollama Online is disabled")
            operation = agent.process_user_request_result(
                request.message,
                request.history,
                session_id=request.session_id,
            )
        return await request_coordinator.run(
            request.coordination_key,
            operation,
            connection=connection,
        )
    except HTTPException:
        raise
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception("Unified MCP request failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


async def _answer(request: ChatRequest, connection: Request | None = None) -> str:
    return (await _answer_result(request, connection)).message


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(render_page(str(OPTIONS.get("web_title") or "Hubitat MCP AI"), VERSION))


@app.get("/health")
async def health() -> dict[str, Any]:
    status = await mcp.health()
    return {
        "status": "ok" if status.get("online") else "degraded",
        "agent": "unified_mcp_agent",
        "version": VERSION,
        "mcp": status,
        "ollama": {
            "enabled": _bool(OPTIONS.get("ollama_direct_cloud_enabled"), True),
            "configured": agent.configured,
            "online": agent.configured,
            "provider": "Ollama Online",
            "model": agent.model_name,
            "local_enabled": _bool(OPTIONS.get("ollama_local_enabled"), False),
            "local_configured": agent.local_configured,
            "local_model": agent.local_model_name or None,
        },
    }


@app.get("/api/status")
async def status() -> dict[str, Any]:
    return await health()


def _normalized_values(device: dict[str, Any]) -> dict[str, Any]:
    values = {**device, **device_attributes(device)}
    return {
        re.sub(r"[^a-z0-9]", "", str(key).lower()): value
        for key, value in values.items()
    }


def _value(values: dict[str, Any], *names: str) -> Any:
    for name in names:
        candidate = values.get(re.sub(r"[^a-z0-9]", "", name.lower()))
        if candidate not in (None, ""):
            return candidate
    return None


def _hub_info(devices: list[dict[str, Any]]) -> dict[str, Any]:
    hub = next(
        (
            device
            for device in devices
            if "hub info"
            in str(device.get("label") or device.get("name") or "").lower()
        ),
        None,
    )
    if hub is None:
        return {}
    values = _normalized_values(hub)
    return {
        "name": _value(values, "name", "label"),
        "model": _value(values, "hubModel", "model"),
        "firmware_version": _value(
            values, "firmwareVersionString", "firmwareVersion"
        ),
        "update_status": _value(values, "hubUpdateStatus", "updateStatus"),
        "update_version": _value(values, "hubUpdateVersion", "availableVersion"),
        "cpu_load": _value(values, "cpu5Min", "cpuLoad", "cpu15Min"),
        "cpu_percent": _value(values, "cpuPct", "cpu15Pct", "loadPct"),
        "free_memory": _value(values, "freeMemory", "freeMem15"),
        "java_free_memory": _value(values, "jvmFree", "javaDirect"),
        "temperature": _value(values, "internalTemp", "temperature"),
        "uptime": _value(values, "formattedUptime", "uptime"),
        "database_size": _value(values, "dbSize", "databaseSize"),
        "ip_address": _value(values, "localIP", "ipAddress"),
        "matter_status": _value(values, "matterStatus"),
    }


@app.get("/api/dashboard")
async def dashboard() -> dict[str, Any]:
    try:
        devices = await mcp.get_cached_devices()
    except Exception as exc:
        logger.warning("Dashboard device enrichment failed: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "devices": None,
            "lights_on": None,
            "motion_active": None,
            "switches_on": None,
            "low_batteries": None,
            "rooms": None,
            "room_counts": [],
            "active_rooms": [],
            "hub_info": {},
        }
    lights_on = motion_active = low_batteries = 0
    room_counts: dict[str, int] = {}
    for device in devices:
        attrs = device_attributes(device)
        room = room_name(device)
        if room:
            room_counts[room] = room_counts.get(room, 0) + 1
        switch = str(attrs.get("switch") or device.get("switch") or "").lower()
        if switch == "on":
            if is_light_device(device):
                lights_on += 1
        if str(attrs.get("motion") or device.get("motion") or "").lower() == "active":
            motion_active += 1
        try:
            battery = float(attrs.get("battery", device.get("battery")))
            if battery <= 20:
                low_batteries += 1
        except (TypeError, ValueError):
            pass
    return {
        "success": True,
        "devices": len(devices),
        "lights_on": lights_on,
        "motion_active": motion_active,
        "switches_on": len(active_non_light_switches(devices)),
        "low_batteries": low_batteries,
        "rooms": len(room_counts),
        "assigned_devices": sum(room_counts.values()),
        "unassigned_devices": len(devices) - sum(room_counts.values()),
        "room_counts": [
            {"name": name, "devices": count}
            for name, count in sorted(room_counts.items(), key=lambda item: item[0].lower())
        ],
        "active_rooms": active_room_summary(devices),
        "hub_info": _hub_info(devices),
    }


@app.get("/api/tools")
async def tools() -> dict[str, Any]:
    values = await mcp.list_tools(refresh=True)
    return {
        "success": True,
        "count": len(values),
        "tools": [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
            }
            for tool in values
        ],
    }


@app.post("/api/refresh")
async def refresh() -> dict[str, Any]:
    await mcp.initialize(force=True)
    values = await mcp.list_tools(refresh=True)
    await mcp.get_cached_devices(refresh=True)
    return {"success": True, "tools": len(values), "version": VERSION}


@app.post("/api/chat")
async def chat(request: ChatRequest, connection: Request) -> dict[str, Any]:
    return {"response": await _answer(request, connection)}


@app.post("/api/ask")
async def ask(request: ChatRequest, connection: Request) -> dict[str, Any]:
    started = time.perf_counter()
    outcome = await _answer_result(request, connection)
    return build_agent_response(
        outcome,
        model=agent.model_name,
        elapsed_ms=round((time.perf_counter() - started) * 1000),
        version=VERSION,
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8788, log_level="info", proxy_headers=True)
