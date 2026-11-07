"""Standalone v2 Home Assistant ingress app: native model-MCP loop + external recorder."""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from agent import Agent
from external_hub_diagnostics import ExternalHubDiagnostics
from mcp import MCPError, ReadOnlyMCP


DEFAULTS: dict[str, Any] = {
    "hubitat_mcp_url": "",
    "hubitat_mcp_token": "",
    "model_base_url": "https://ollama.com",
    "model_name": "gemma4:31b-cloud",
    "model_api_key": "",
    "model_timeout_seconds": 120,
    "mcp_timeout_seconds": 25,
    "investigation_timeout_seconds": 300,
    "external_hub_diagnostics_enabled": False,
    "external_hub_diagnostics_hub_url": "",
    "external_hub_diagnostics_probe_seconds": 30,
    "external_hub_diagnostics_cpu_cores": 4,
    "external_hub_diagnostics_retention_days": 30,
}


def config(path: Path = Path("/data/options.json")) -> dict:
    result = dict(DEFAULTS)
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(saved, dict):
            raise ValueError("Invalid add-on options")
        result.update({key: saved[key] for key in DEFAULTS if key in saved})
    return result


def http_base(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc or parts.username or parts.password:
        raise ValueError("Model base URL must be HTTP(S) without embedded credentials")
    if parts.query or parts.fragment:
        raise ValueError("Model base URL must not contain a query or fragment")
    return url.rstrip("/")


@asynccontextmanager
async def lifecycle(app: FastAPI):
    options = config()
    app.state.options = options
    app.state.ask_lock = asyncio.Lock()
    app.state.mcp = None
    app.state.model = None
    app.state.configuration_error = None
    try:
        app.state.model = Agent(
            http_base(str(options["model_base_url"])),
            str(options["model_name"]),
            str(options["model_api_key"]),
            int(options["model_timeout_seconds"]),
        )
        if str(options["hubitat_mcp_url"]).strip():
            app.state.mcp = ReadOnlyMCP(
                str(options["hubitat_mcp_url"]),
                str(options["hubitat_mcp_token"]),
                int(options["mcp_timeout_seconds"]),
            )
    except (MCPError, ValueError) as exc:
        app.state.configuration_error = str(exc)
    app.state.recorder = ExternalHubDiagnostics(
        enabled=bool(options["external_hub_diagnostics_enabled"]),
        hub_url=str(options["external_hub_diagnostics_hub_url"]),
        path="/data/hubitat-mcp-ai-v2-diagnostics.sqlite3",
        probe_seconds=int(options["external_hub_diagnostics_probe_seconds"]),
        cpu_cores=int(options["external_hub_diagnostics_cpu_cores"]),
        retention_days=int(options["external_hub_diagnostics_retention_days"]),
    )
    await app.state.recorder.start()
    try:
        yield
    finally:
        await app.state.recorder.close()
        if app.state.mcp:
            await app.state.mcp.close()
        if app.state.model:
            await app.state.model.close()


app = FastAPI(title="Hubitat MCP AI v2", version="2.0.0-alpha.1", lifespan=lifecycle)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=10000)
    history: list[dict] = Field(default_factory=list, max_length=20)


@app.get("/")
async def index():
    return FileResponse(Path(__file__).parent / "ui.html", media_type="text/html")


@app.get("/api/status")
async def status():
    options = app.state.options
    mcp: ReadOnlyMCP | None = app.state.mcp
    return {
        "version": "2.0.0-alpha.1",
        "mode": "native-model-led-read-only",
        "configured": bool(mcp and app.state.model),
        "configuration_error": app.state.configuration_error,
        "model": str(options["model_name"]),
        "recorder": app.state.recorder.status(),
    }


@app.post("/api/ask")
async def ask(request: AskRequest):
    if app.state.configuration_error:
        raise HTTPException(503, app.state.configuration_error)
    if app.state.mcp is None or app.state.model is None:
        raise HTTPException(503, "Configure the model and Hubitat MCP URL in add-on options")
    async with app.state.ask_lock:
        try:
            return await app.state.model.answer(
                request.question, request.history,
                app.state.mcp, int(app.state.options["investigation_timeout_seconds"]),
            )
        except MCPError as exc:
            return {"success": False, "answer": f"MCP connection/read failure: {exc}",
                    "tool_calls": [], "error": "mcp"}
        except RuntimeError as exc:
            return {"success": False, "answer": f"Model/transport failure: {exc}",
                    "tool_calls": [], "error": "model"}


@app.get("/api/diagnostics/status")
async def diagnostic_status():
    return app.state.recorder.status()


@app.get("/api/diagnostics/history")
async def diagnostic_history(hours: int = 24, metric: str = "free_os_mb"):
    try:
        return app.state.recorder.history(hours=hours, metric=metric)
    except ValueError:
        raise HTTPException(400, "Unsupported recorder metric") from None


@app.get("/api/diagnostics/timeline")
async def diagnostic_timeline(hours: int = 24):
    return app.state.recorder.timeline(hours=hours)
