from __future__ import annotations

import json
import logging
import os
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
        "gemini_enabled": True,
        "gemini_base_url": "https://generativelanguage.googleapis.com/v1beta",
        "gemini_api_key": "",
        "gemini_model": "gemini-3.6-flash",
        "gemini_timeout_seconds": 15,
        "mcp_timeout_seconds": 25,
        "mcp_device_cache_seconds": 12,
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
    gemini_api_key=str(OPTIONS.get("gemini_api_key") or ""),
    model_name=str(OPTIONS.get("gemini_model") or "gemini-3.6-flash"),
    gemini_base_url=str(
        OPTIONS.get("gemini_base_url")
        or "https://generativelanguage.googleapis.com/v1beta"
    ),
    timeout_seconds=float(OPTIONS.get("gemini_timeout_seconds") or 15),
    tool_limit=int(OPTIONS.get("unified_mcp_tool_limit") or 48),
    require_sensitive_confirmation=_bool(
        OPTIONS.get("require_sensitive_confirmation"), True
    ),
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
    if not _bool(OPTIONS.get("gemini_enabled"), True):
        raise HTTPException(status_code=503, detail="Gemini is disabled")
    try:
        return await agent.process_user_request(request.message, request.history)
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
        "gemini_configured": bool(OPTIONS.get("gemini_api_key")),
    }


@app.get("/api/status")
async def status() -> dict[str, Any]:
    return await health()


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


@app.post("/api/chat")
async def chat(request: ChatRequest) -> dict[str, Any]:
    return {"response": await _answer(request)}


@app.post("/api/ask")
async def ask(request: ChatRequest) -> dict[str, Any]:
    message = await _answer(request)
    return {
        "success": True,
        "route": "unified-mcp-agent",
        "intent": "native-function-calling",
        "message": message,
        "version": VERSION,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8788, log_level="info", proxy_headers=True)
