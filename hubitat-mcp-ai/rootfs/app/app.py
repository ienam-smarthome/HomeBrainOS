from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from fast_fallback import FastFallbackRouter
from mcp_client import HubitatMCPClient
from ollama_agent_fast import OllamaMCPAgent, OllamaUnavailable
from routing import dedupe_current_query, is_control_query, is_fast_path_query
from webui import render_page


VERSION = "0.1.3-alpha"
OPTIONS_PATH = Path("/data/options.json")


def load_options() -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "hubitat_mcp_url": "",
        "hubitat_mcp_token": "",
        "ollama_enabled": True,
        "ollama_base_url": "http://homeassistant.local:11434",
        "ollama_model": "qwen2.5:3b",
        "ollama_timeout_seconds": 35,
        "ollama_total_timeout_seconds": 40,
        "ollama_health_timeout_seconds": 3,
        "ollama_num_ctx": 4096,
        "ollama_num_predict": 160,
        "ollama_keep_alive": "15m",
        "ollama_tool_limit": 10,
        "ollama_max_tool_rounds": 3,
        "fast_path_enabled": True,
        "fallback_enabled": True,
        "mcp_timeout_seconds": 25,
        "require_sensitive_confirmation": True,
        "web_title": "Hubitat MCP AI",
    }
    if OPTIONS_PATH.exists():
        try:
            value = json.loads(OPTIONS_PATH.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                defaults.update(value)
        except Exception:
            pass
    for key in list(defaults):
        env_key = f"HMCP_{key.upper()}"
        if env_key in os.environ:
            defaults[key] = os.environ[env_key]
    return defaults


def option_bool(name: str, default: bool = False) -> bool:
    value = OPTIONS.get(name, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


OPTIONS = load_options()

mcp = HubitatMCPClient(
    endpoint_url=str(OPTIONS.get("hubitat_mcp_url") or ""),
    access_token=str(OPTIONS.get("hubitat_mcp_token") or ""),
    timeout_seconds=float(OPTIONS.get("mcp_timeout_seconds") or 25),
)
ollama = OllamaMCPAgent(
    client=mcp,
    base_url=str(OPTIONS.get("ollama_base_url") or ""),
    model=str(OPTIONS.get("ollama_model") or ""),
    timeout_seconds=float(OPTIONS.get("ollama_timeout_seconds") or 35),
    health_timeout_seconds=float(OPTIONS.get("ollama_health_timeout_seconds") or 3),
    num_ctx=int(OPTIONS.get("ollama_num_ctx") or 4096),
    num_predict=int(OPTIONS.get("ollama_num_predict") or 160),
    keep_alive=str(OPTIONS.get("ollama_keep_alive") or "15m"),
    tool_limit=int(OPTIONS.get("ollama_tool_limit") or 10),
    max_tool_rounds=int(OPTIONS.get("ollama_max_tool_rounds") or 3),
    require_sensitive_confirmation=option_bool(
        "require_sensitive_confirmation",
        True,
    ),
)
fallback = FastFallbackRouter(mcp)

app = FastAPI(
    title=str(OPTIONS.get("web_title") or "Hubitat MCP AI"),
    version=VERSION,
)


class HistoryItem(BaseModel):
    role: str
    content: str


class AskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    history: list[HistoryItem] = Field(default_factory=list)


def elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(
        render_page(
            str(OPTIONS.get("web_title") or "Hubitat MCP AI"),
            VERSION,
        )
    )


@app.get("/api/status")
async def status() -> dict[str, Any]:
    mcp_status, ollama_status = await asyncio.gather(
        mcp.health(),
        ollama.health(),
        return_exceptions=True,
    )
    if isinstance(mcp_status, Exception):
        mcp_status = {"online": False, "error": str(mcp_status)}
    if isinstance(ollama_status, Exception):
        ollama_status = {"online": False, "error": str(ollama_status)}
    if not option_bool("ollama_enabled", True):
        ollama_status = {
            "online": False,
            "disabled": True,
            "model": OPTIONS.get("ollama_model"),
        }
    return {
        "success": True,
        "version": VERSION,
        "mcp": mcp_status,
        "ollama": ollama_status,
        "fast_path_enabled": option_bool("fast_path_enabled", True),
        "fallback_enabled": option_bool("fallback_enabled", True),
        "ollama_total_timeout_seconds": float(
            OPTIONS.get("ollama_total_timeout_seconds") or 40
        ),
    }


@app.post("/api/ask")
async def ask(request: AskRequest) -> dict[str, Any]:
    started = time.perf_counter()
    query = request.query.strip()
    raw_history = [
        {"role": item.role, "content": item.content}
        for item in request.history[-10:]
    ]
    history = dedupe_current_query(raw_history, query)

    fallback_enabled = option_bool("fallback_enabled", True)
    fast_path_enabled = option_bool("fast_path_enabled", True)
    fast_path_error: str | None = None

    if fallback_enabled and fast_path_enabled and is_fast_path_query(query):
        try:
            answer = await asyncio.wait_for(
                fallback.answer(query),
                timeout=float(OPTIONS.get("mcp_timeout_seconds") or 25) + 5,
            )
            answer["route"] = "mcp-fast"
            answer["version"] = VERSION
            answer["elapsed_ms"] = elapsed_ms(started)
            if answer.get("success") or is_control_query(query):
                return answer
            fast_path_error = str(answer.get("message") or "Fast path did not answer")
        except Exception as exc:
            fast_path_error = str(exc)

    ollama_error = "Ollama is disabled"
    if option_bool("ollama_enabled", True):
        total_timeout = max(
            8.0,
            float(OPTIONS.get("ollama_total_timeout_seconds") or 40),
        )
        try:
            answer = await asyncio.wait_for(
                ollama.answer(query, history),
                timeout=total_timeout,
            )
            answer.setdefault("version", VERSION)
            answer["elapsed_ms"] = elapsed_ms(started)
            if answer.get("success", True):
                return answer
            ollama_error = str(
                answer.get("message") or "Ollama tool loop did not finish"
            )
        except asyncio.TimeoutError:
            ollama_error = (
                f"Ollama exceeded the {total_timeout:g}s total response budget"
            )
        except OllamaUnavailable as exc:
            ollama_error = str(exc)
        except Exception as exc:
            ollama_error = str(exc)

    if fallback_enabled:
        answer = await fallback.answer(query)
        answer["route"] = "fallback"
        answer["ollama_error"] = ollama_error
        answer["fast_path_error"] = fast_path_error
        answer["version"] = VERSION
        answer["elapsed_ms"] = elapsed_ms(started)
        return answer

    raise HTTPException(
        status_code=503,
        detail=f"Ollama is unavailable and fallback is disabled: {ollama_error}",
    )


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
    ollama_status = await ollama.health(force=True)
    return {
        "success": True,
        "tools": len(values),
        "ollama": ollama_status,
    }


@app.on_event("shutdown")
async def shutdown() -> None:
    await mcp.close()
    await ollama.close()


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8788,
        log_level="info",
        proxy_headers=True,
    )
