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

from fast_fallback_device_health import FastFallbackRouter
from mcp_client import HubitatMCPClient
from ollama_agent_claude import ClaudeStyleOllamaAgent, OllamaUnavailable
from request_router import run_fast_path
from routing import dedupe_current_query, is_fast_path_query
from webui import render_page


VERSION = "0.2.0-alpha"
OPTIONS_PATH = Path("/data/options.json")


def load_options() -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "hubitat_mcp_url": "",
        "hubitat_mcp_token": "",
        "ollama_enabled": True,
        "ollama_base_url": "http://homeassistant.local:11434",
        "ollama_model": "qwen3.5:9b",
        "ollama_planner_model": "",
        "ollama_health_timeout_seconds": 3,
        "ollama_planner_timeout_seconds": 45,
        "ollama_response_timeout_seconds": 90,
        "ollama_agent_timeout_seconds": 150,
        "ollama_num_ctx": 4096,
        "ollama_num_predict": 220,
        "ollama_keep_alive": "30m",
        "ollama_planner_tool_limit": 6,
        "ollama_tool_result_limit_chars": 12000,
        "ollama_max_tool_rounds": 3,
        "fast_path_enabled": True,
        "fallback_enabled": True,
        "mcp_timeout_seconds": 25,
        "attention_stale_hours": 48,
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


def normalise_query(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def is_ollama_diagnostics_query(query: str) -> bool:
    q = normalise_query(query)
    return "ollama" in q and any(
        term in q
        for term in (
            "status",
            "health",
            "diagnostic",
            "ready",
            "online",
            "model",
            "loaded",
            "inference",
        )
    )


OPTIONS = load_options()

mcp = HubitatMCPClient(
    endpoint_url=str(OPTIONS.get("hubitat_mcp_url") or ""),
    access_token=str(OPTIONS.get("hubitat_mcp_token") or ""),
    timeout_seconds=float(OPTIONS.get("mcp_timeout_seconds") or 25),
)
ollama = ClaudeStyleOllamaAgent(
    client=mcp,
    base_url=str(OPTIONS.get("ollama_base_url") or ""),
    model=str(OPTIONS.get("ollama_model") or ""),
    planner_model=str(OPTIONS.get("ollama_planner_model") or ""),
    health_timeout_seconds=float(OPTIONS.get("ollama_health_timeout_seconds") or 3),
    planner_timeout_seconds=float(
        OPTIONS.get("ollama_planner_timeout_seconds") or 45
    ),
    response_timeout_seconds=float(
        OPTIONS.get("ollama_response_timeout_seconds") or 90
    ),
    num_ctx=int(OPTIONS.get("ollama_num_ctx") or 4096),
    num_predict=int(OPTIONS.get("ollama_num_predict") or 220),
    keep_alive=str(OPTIONS.get("ollama_keep_alive") or "30m"),
    planner_tool_limit=int(OPTIONS.get("ollama_planner_tool_limit") or 6),
    tool_result_limit_chars=int(
        OPTIONS.get("ollama_tool_result_limit_chars") or 12000
    ),
    max_tool_rounds=int(OPTIONS.get("ollama_max_tool_rounds") or 3),
    require_sensitive_confirmation=option_bool(
        "require_sensitive_confirmation",
        True,
    ),
)
fallback = FastFallbackRouter(
    mcp,
    attention_stale_hours=float(OPTIONS.get("attention_stale_hours") or 48),
)

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


def compatibility_inference(runtime: dict[str, Any]) -> dict[str, Any]:
    if not runtime.get("online"):
        return {
            "ready": False,
            "state": "server-offline",
            "model": runtime.get("model"),
            "message": runtime.get("error") or "Ollama server is unreachable.",
        }
    if not runtime.get("model_present"):
        return {
            "ready": False,
            "state": "missing",
            "model": runtime.get("model"),
            "message": "The configured response model is not installed.",
        }
    if runtime.get("model_loaded"):
        return {
            "ready": True,
            "state": "ready",
            "model": runtime.get("model"),
            "message": "The response model is loaded and ready.",
        }
    return {
        "ready": None,
        "state": "available",
        "model": runtime.get("model"),
        "message": "The model is installed and will load on the next AI question.",
    }


async def build_ollama_diagnostics(force: bool = False) -> dict[str, Any]:
    if not option_bool("ollama_enabled", True):
        runtime = {
            "online": False,
            "disabled": True,
            "model": OPTIONS.get("ollama_model"),
            "error": "Ollama is disabled in add-on configuration.",
            "loaded_models": [],
            "installed_models": [],
            "last_agent": {"state": "disabled"},
        }
    else:
        runtime = await ollama.runtime_status(force=force)

    server_text = "Online" if runtime.get("online") else "Offline"
    model_text = str(runtime.get("model") or "—")
    model_state = (
        "Loaded"
        if runtime.get("model_loaded")
        else "Available"
        if runtime.get("model_present")
        else "Missing"
    )
    planner_text = str(runtime.get("planner_model") or model_text)
    last_agent = runtime.get("last_agent") or {}
    last_state = str(last_agent.get("state") or "idle").replace("-", " ").title()

    lines = [
        f"Ollama server: {server_text}",
        f"Response model: {model_text} ({model_state.lower()})",
        f"Planner model: {planner_text}",
        f"Last agent state: {last_state}",
    ]
    if last_agent.get("elapsed_ms") is not None:
        lines.append(f"Last agent time: {float(last_agent['elapsed_ms']) / 1000:.1f}s")
    if last_agent.get("error"):
        lines.append(f"Last agent error: {last_agent['error']}")
    if runtime.get("error"):
        lines.append(f"Server error: {runtime['error']}")

    metrics = [
        {
            "label": "Server",
            "value": server_text,
            "icon": "🟢" if runtime.get("online") else "🔴",
        },
        {
            "label": "Response model",
            "value": model_state,
            "icon": "🧠",
        },
        {
            "label": "Planner",
            "value": planner_text,
            "icon": "🧭",
        },
        {
            "label": "Last agent",
            "value": last_state,
            "icon": "🤖",
        },
        {
            "label": "Fast path",
            "value": "On/off only",
            "icon": "⚡",
        },
    ]

    return {
        "success": bool(runtime.get("online")),
        "route": "system",
        "intent": "ollama-diagnostics",
        "message": "\n".join(lines),
        "model": model_text,
        "runtime": runtime,
        "inference": compatibility_inference(runtime),
        "display": {
            "kind": "ollama-diagnostics",
            "title": "Ollama diagnostics",
            "subtitle": f"Server {server_text.lower()} · model {model_state.lower()}",
            "metrics": metrics,
            "items": [],
            "note": (
                "Model availability is read from /api/tags and loaded state from /api/ps. "
                "Real questions are no longer blocked by a synthetic readiness probe."
            ),
        },
        "technical": json.dumps(runtime, ensure_ascii=False, indent=2, default=str),
        "version": VERSION,
    }


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
    mcp_status, runtime = await asyncio.gather(
        mcp.health(),
        ollama.runtime_status(),
        return_exceptions=True,
    )
    if isinstance(mcp_status, Exception):
        mcp_status = {"online": False, "error": str(mcp_status)}
    if isinstance(runtime, Exception):
        runtime = {
            "online": False,
            "model": OPTIONS.get("ollama_model"),
            "error": str(runtime),
        }
    if not option_bool("ollama_enabled", True):
        runtime = {
            "online": False,
            "disabled": True,
            "model": OPTIONS.get("ollama_model"),
            "error": "Ollama is disabled",
        }

    return {
        "success": True,
        "version": VERSION,
        "mcp": mcp_status,
        "ollama": runtime,
        "ollama_inference": compatibility_inference(runtime),
        "fast_path_enabled": option_bool("fast_path_enabled", True),
        "fast_path_scope": "explicit on/off commands only",
        "fallback_enabled": option_bool("fallback_enabled", True),
        "ollama_agent_timeout_seconds": float(
            OPTIONS.get("ollama_agent_timeout_seconds") or 150
        ),
    }


@app.get("/api/ollama-diagnostics")
async def ollama_diagnostics(force: bool = False) -> dict[str, Any]:
    return await build_ollama_diagnostics(force=force)


@app.post("/api/ask")
async def ask(request: AskRequest) -> dict[str, Any]:
    started = time.perf_counter()
    query = request.query.strip()
    raw_history = [
        {"role": item.role, "content": item.content}
        for item in request.history[-10:]
    ]
    history = dedupe_current_query(raw_history, query)

    if is_ollama_diagnostics_query(query):
        answer = await build_ollama_diagnostics(force=False)
        answer["elapsed_ms"] = elapsed_ms(started)
        return answer

    fallback_enabled = option_bool("fallback_enabled", True)
    fast_path_enabled = option_bool("fast_path_enabled", True)

    # Deliberately narrow: deterministic routing is only for explicit, low-risk
    # on/off commands. Everything else uses the natural Ollama MCP agent.
    if fallback_enabled and fast_path_enabled and is_fast_path_query(query):
        answer = await run_fast_path(
            query,
            fallback,
            timeout_seconds=float(OPTIONS.get("mcp_timeout_seconds") or 25),
            retries=1,
        )
        answer["route"] = "mcp-fast"
        answer["version"] = VERSION
        answer["elapsed_ms"] = elapsed_ms(started)
        return answer

    ollama_error = "Ollama is disabled"
    if option_bool("ollama_enabled", True):
        agent_timeout = max(
            30.0,
            float(OPTIONS.get("ollama_agent_timeout_seconds") or 150),
        )
        try:
            answer = await asyncio.wait_for(
                ollama.answer(query, history),
                timeout=agent_timeout,
            )
            answer.setdefault("version", VERSION)
            answer["elapsed_ms"] = elapsed_ms(started)
            if answer.get("success", True):
                return answer
            ollama_error = str(answer.get("message") or "Ollama agent did not finish")
        except asyncio.TimeoutError:
            ollama_error = f"Ollama agent exceeded the {agent_timeout:g}s response budget"
        except OllamaUnavailable as exc:
            ollama_error = str(exc)
        except Exception as exc:
            ollama_error = str(exc)

    if fallback_enabled:
        answer = await fallback.answer(query)
        answer["route"] = "fallback"
        answer["ollama_error"] = ollama_error
        answer["version"] = VERSION
        answer["elapsed_ms"] = elapsed_ms(started)
        answer["fallback_reason"] = (
            f"The Ollama-first agent could not complete this request: {ollama_error}"
        )
        if answer.get("intent") == "fallback-unsupported":
            answer["message"] = (
                "The natural Ollama agent could not complete the request, and the local "
                "fallback does not support this question.\n\n"
                f"Ollama error: {ollama_error}"
            )
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
    runtime = await ollama.runtime_status(force=True)
    return {
        "success": True,
        "tools": len(values),
        "ollama": runtime,
        "ollama_inference": compatibility_inference(runtime),
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
