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
from ollama_agent_inference import OllamaMCPAgent, OllamaUnavailable
from request_router import run_fast_path, schedule_background_health_check
from routing import dedupe_current_query, is_fast_path_query
from webui import render_page


VERSION = "0.1.11-alpha"
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
        "ollama_inference_probe_timeout_seconds": 20,
        "ollama_inference_failure_ttl_seconds": 60,
        "ollama_num_ctx": 4096,
        "ollama_num_predict": 160,
        "ollama_keep_alive": "15m",
        "ollama_tool_limit": 10,
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
            "inference",
        )
    )


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
    inference_probe_timeout_seconds=float(
        OPTIONS.get("ollama_inference_probe_timeout_seconds") or 20
    ),
    inference_failure_ttl_seconds=float(
        OPTIONS.get("ollama_inference_failure_ttl_seconds") or 60
    ),
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


def inference_label(status: dict[str, Any]) -> str:
    state = str(status.get("state") or "unknown")
    return {
        "ready": "Ready",
        "timeout": "Timed out",
        "error": "Failed",
        "server-offline": "Server offline",
        "retry-due": "Rechecking",
        "unknown": "Not checked",
    }.get(state, state.replace("-", " ").title())


async def build_ollama_diagnostics(force_probe: bool = False) -> dict[str, Any]:
    if not option_bool("ollama_enabled", True):
        server = {
            "online": False,
            "disabled": True,
            "model": OPTIONS.get("ollama_model"),
            "error": "Ollama is disabled",
        }
        inference = {
            "ready": False,
            "state": "disabled",
            "model": OPTIONS.get("ollama_model"),
            "message": "Ollama is disabled in add-on configuration.",
        }
    else:
        server = await ollama.health(force=force_probe)
        if force_probe and server.get("online"):
            inference = await ollama.probe_inference(force=True)
        else:
            inference = ollama.inference_status()
            if server.get("online") and ollama.inference_probe_due():
                ollama.schedule_inference_probe()
                inference = ollama.inference_status()

    server_text = "Online" if server.get("online") else "Offline"
    inference_text = inference_label(inference)
    model = str(server.get("model") or inference.get("model") or ollama.model or "—")
    last_ms = inference.get("elapsed_ms")
    age = inference.get("age_seconds")

    lines = [
        f"Ollama server: {server_text}",
        f"Model: {model}",
        f"Model inference: {inference_text}",
    ]
    if last_ms is not None:
        lines.append(f"Latest inference check: {float(last_ms) / 1000:.1f}s")
    if inference.get("message"):
        lines.append(str(inference["message"]))
    if server.get("error"):
        lines.append(f"Server error: {server['error']}")
    if inference.get("error"):
        lines.append(f"Chat error: {inference['error']}")

    metrics = [
        {
            "label": "Server",
            "value": server_text,
            "icon": "🟢" if server.get("online") else "🔴",
        },
        {
            "label": "Inference",
            "value": inference_text,
            "icon": "🧠",
        },
        {
            "label": "Model",
            "value": model,
            "icon": "🤖",
        },
        {
            "label": "Failure cache",
            "value": f"{int(ollama.inference_failure_ttl_seconds)}s",
            "icon": "⏱️",
        },
    ]
    if last_ms is not None:
        metrics.append(
            {
                "label": "Latest inference",
                "value": f"{float(last_ms) / 1000:.1f}s",
                "icon": "⚡",
            }
        )
    if age is not None:
        metrics.append(
            {
                "label": "Checked",
                "value": f"{age:g}s ago",
                "icon": "🕒",
            }
        )

    return {
        "success": bool(server.get("online")),
        "route": "system",
        "intent": "ollama-diagnostics",
        "message": "\n".join(lines),
        "model": model,
        "server": server,
        "inference": inference,
        "display": {
            "kind": "ollama-diagnostics",
            "title": "Ollama diagnostics",
            "subtitle": (
                f"Server {server_text.lower()} · inference {inference_text.lower()}"
            ),
            "metrics": metrics,
            "items": [],
            "note": (
                "The server check uses /api/tags. Inference readiness uses a small /api/chat request."
            ),
        },
        "technical": json.dumps(
            {"server": server, "inference": inference},
            ensure_ascii=False,
            indent=2,
        ),
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

    inference = ollama.inference_status()
    if (
        option_bool("ollama_enabled", True)
        and isinstance(ollama_status, dict)
        and ollama_status.get("online")
        and ollama.inference_probe_due()
    ):
        ollama.schedule_inference_probe()
        inference = ollama.inference_status()

    return {
        "success": True,
        "version": VERSION,
        "mcp": mcp_status,
        "ollama": ollama_status,
        "ollama_inference": inference,
        "fast_path_enabled": option_bool("fast_path_enabled", True),
        "fallback_enabled": option_bool("fallback_enabled", True),
        "ollama_total_timeout_seconds": float(
            OPTIONS.get("ollama_total_timeout_seconds") or 40
        ),
    }


@app.get("/api/ollama-diagnostics")
async def ollama_diagnostics(probe: bool = False) -> dict[str, Any]:
    return await build_ollama_diagnostics(force_probe=probe)


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
        answer = await build_ollama_diagnostics(force_probe=False)
        answer["elapsed_ms"] = elapsed_ms(started)
        return answer

    fallback_enabled = option_bool("fallback_enabled", True)
    fast_path_enabled = option_bool("fast_path_enabled", True)

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

        if option_bool("ollama_enabled", True):
            asyncio.create_task(schedule_background_health_check(ollama.health))
            ollama.schedule_inference_probe()
        return answer

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
            ollama.record_inference_failure(
                ollama_error,
                state="error",
                elapsed_ms=elapsed_ms(started),
            )
        except asyncio.TimeoutError:
            ollama_error = (
                f"Ollama exceeded the {total_timeout:g}s total response budget"
            )
            ollama.record_inference_failure(
                ollama_error,
                state="timeout",
                elapsed_ms=elapsed_ms(started),
            )
        except OllamaUnavailable as exc:
            ollama_error = str(exc)
        except Exception as exc:
            ollama_error = str(exc)
            ollama.record_inference_failure(
                ollama_error,
                state="error",
                elapsed_ms=elapsed_ms(started),
            )

    if fallback_enabled:
        answer = await fallback.answer(query)
        answer["route"] = "fallback"
        answer["ollama_error"] = ollama_error
        answer["fallback_reason"] = ollama.fallback_reason()
        answer["ollama_inference"] = ollama.inference_status()
        answer["version"] = VERSION
        answer["elapsed_ms"] = elapsed_ms(started)
        if answer.get("intent") == "fallback-unsupported":
            answer["message"] = (
                ollama.fallback_reason()
                + "\n\n"
                + "The fallback currently handles device on/off, lights and switches on, "
                "low batteries, device health, weather, rooms, home status, and hub health."
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
    ollama_status = await ollama.health(force=True)
    inference = (
        await ollama.probe_inference(force=True)
        if option_bool("ollama_enabled", True)
        else ollama.inference_status()
    )
    return {
        "success": True,
        "tools": len(values),
        "ollama": ollama_status,
        "ollama_inference": inference,
    }


@app.on_event("startup")
async def startup() -> None:
    if option_bool("ollama_enabled", True):
        ollama.schedule_inference_probe(force=True)


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
