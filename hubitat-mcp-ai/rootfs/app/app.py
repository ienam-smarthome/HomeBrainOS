from __future__ import annotations

import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, model_validator

from mcp_agent_orchestrator import UnifiedMCPAgent
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
        "ollama_direct_cloud_model": "gemma4:31b",
        "ollama_cloud_model": "gemma4:31b-cloud",
        "ollama_agent_timeout_seconds": 60,
        "mcp_timeout_seconds": 25,
        "mcp_device_cache_seconds": 12,
        "confirmation_ttl_seconds": 120,
        "unified_mcp_tool_limit": 48,
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
)
agent = UnifiedMCPAgent(
    mcp_client=mcp,
    api_key=str(OPTIONS.get("ollama_direct_cloud_api_key") or ""),
    model_name=str(
        OPTIONS.get("ollama_direct_cloud_model")
        or OPTIONS.get("ollama_cloud_model")
        or "gemma4:31b"
    ),
    base_url=str(OPTIONS.get("ollama_direct_cloud_base_url") or "https://ollama.com"),
    timeout_seconds=float(OPTIONS.get("ollama_agent_timeout_seconds") or 60),
    tool_limit=int(OPTIONS.get("unified_mcp_tool_limit") or 48),
    require_sensitive_confirmation=_bool(
        OPTIONS.get("require_sensitive_confirmation"), True
    ),
    confirmation_ttl_seconds=float(OPTIONS.get("confirmation_ttl_seconds") or 120),
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        yield
    finally:
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

    @model_validator(mode="after")
    def require_message(self) -> "ChatRequest":
        value = (self.prompt or self.query or "").strip()
        if not value:
            raise ValueError("Prompt required")
        return self

    @property
    def message(self) -> str:
        return (self.prompt or self.query or "").strip()


async def _answer(request: ChatRequest) -> str:
    if not _bool(OPTIONS.get("ollama_direct_cloud_enabled"), True):
        raise HTTPException(status_code=503, detail="Ollama Online is disabled")
    try:
        return await agent.process_user_request(
            request.message,
            request.history,
            session_id=request.session_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unified MCP request failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


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
        },
    }


@app.get("/api/status")
async def status() -> dict[str, Any]:
    return await health()


@app.get("/api/dashboard")
async def dashboard() -> dict[str, Any]:
    devices = await mcp.get_cached_devices()
    lights_on = motion_active = switches_on = low_batteries = 0
    for device in devices:
        attrs = device.get("attributes") or device.get("states") or {}
        if isinstance(attrs, list):
            attrs = {
                str(item.get("name")): item.get("currentValue", item.get("value"))
                for item in attrs if isinstance(item, dict) and item.get("name")
            }
        if not isinstance(attrs, dict):
            attrs = {}
        capabilities = " ".join(map(str, device.get("capabilities") or [])).lower()
        switch = str(attrs.get("switch") or device.get("switch") or "").lower()
        if switch == "on":
            if "light" in capabilities or "bulb" in capabilities:
                lights_on += 1
            else:
                switches_on += 1
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
        "switches_on": switches_on,
        "low_batteries": low_batteries,
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
async def chat(request: ChatRequest) -> dict[str, Any]:
    return {"response": await _answer(request)}


@app.post("/api/ask")
async def ask(request: ChatRequest) -> dict[str, Any]:
    started = time.perf_counter()
    message = await _answer(request)
    return {
        "success": True,
        "route": "unified-mcp-agent",
        "intent": "native-function-calling",
        "message": message,
        "model": agent.model_name,
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
        "version": VERSION,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8788, log_level="info", proxy_headers=True)
