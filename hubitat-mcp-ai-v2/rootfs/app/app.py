"""Standalone v2 Home Assistant ingress app: native model-MCP loop + external recorder."""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from benchmark import BenchmarkWorkspace
from benchmark_routes import router as benchmark_router
from autonomous_lab import AutonomousLab
from autonomous_routes import router as autonomous_router
from reasoning_experiment import ReasoningExperiment
from reasoning_routes import router as reasoning_router
from prospective_routes import router as prospective_router
from prospective_source_ab import ProspectiveWorkspace
from pydantic import BaseModel, Field, StrictBool

from agent import Agent
from external_hub_diagnostics import ExternalHubDiagnostics
from device_monitor import HubDeviceMonitor
from home_overview import OverviewUnavailable, read_overview
from home_assistant_tts import HomeAssistantTTS, HomeAssistantTTSConfigurationError
from mcp import MCPError, MCPClient
from interaction import Interaction
from conversation import ConversationEvidence
from frozen_evaluation import FrozenEvaluationError, freeze_capture, replay_frozen_capture


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
    "external_hub_diagnostics_hub_timezone": "Europe/London",
    "external_hub_diagnostics_retention_days": 30,
    "device_monitor_enabled": False,
    "device_monitor_api_base": "",
    "device_monitor_access_token": "",
    "ha_tts_enabled": False,
    "ha_tts_notify_service": "",
    "ha_tts_media_stream": "",
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
    app.state.interactions = {}
    app.state.conversations = ConversationEvidence()
    app.state.benchmark = BenchmarkWorkspace(Path("/data/homebrain-v2-benchmark"))
    app.state.benchmark_task = None
    app.state.benchmark_progress = {"running": False, "error": None}
    app.state.autolab = AutonomousLab(Path("/data/homebrain-v2-autonomous-lab"))
    app.state.autolab_task = None
    app.state.autolab_progress = {"running": False, "error": None}
    app.state.reasoning_lab = ReasoningExperiment(Path("/data/homebrain-v2-reasoning-ab"))
    app.state.prospective = ProspectiveWorkspace()
    app.state.prospective_task = None
    app.state.reasoning_task = None
    app.state.reasoning_progress = {"running": False, "error": None}
    app.state.mcp = None
    app.state.model = None
    app.state.configuration_error = None
    app.state.device_monitor = None
    app.state.device_monitor_error = None
    if bool(options["device_monitor_enabled"]):
        try:
            app.state.device_monitor = HubDeviceMonitor(
                str(options["device_monitor_api_base"]),
                str(options["device_monitor_access_token"]),
            )
        except ValueError as exc:
            # The optional monitor does not prevent normal model/MCP reads.
            app.state.device_monitor_error = str(exc)
    app.state.tts = HomeAssistantTTS(
        enabled=bool(options["ha_tts_enabled"]),
        supervisor_token=str(os.getenv("SUPERVISOR_TOKEN") or os.getenv("HASSIO_TOKEN") or ""),
        notify_service=str(options["ha_tts_notify_service"]),
        media_stream=str(options["ha_tts_media_stream"]),
    )
    try:
        app.state.model = Agent(
            http_base(str(options["model_base_url"])),
            str(options["model_name"]),
            str(options["model_api_key"]),
            int(options["model_timeout_seconds"]),
            cpu_cores=int(options["external_hub_diagnostics_cpu_cores"]),
        )
        if str(options["hubitat_mcp_url"]).strip():
            app.state.mcp = MCPClient(
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
        hub_timezone=str(options["external_hub_diagnostics_hub_timezone"]),
        retention_days=int(options["external_hub_diagnostics_retention_days"]),
    )
    await app.state.recorder.start()
    try:
        yield
    finally:
        if app.state.prospective_task and not app.state.prospective_task.done():
            app.state.prospective_task.cancel()
            try:
                await app.state.prospective_task
            except asyncio.CancelledError:
                pass
        if app.state.reasoning_task and not app.state.reasoning_task.done():
            app.state.reasoning_task.cancel()
            try:
                await app.state.reasoning_task
            except asyncio.CancelledError:
                pass
        if app.state.autolab_task and not app.state.autolab_task.done():
            app.state.autolab_task.cancel()
            try:
                await app.state.autolab_task
            except asyncio.CancelledError:
                pass
        if app.state.benchmark_task and not app.state.benchmark_task.done():
            app.state.benchmark_task.cancel()
            try:
                await app.state.benchmark_task
            except asyncio.CancelledError:
                pass
        await app.state.recorder.close()
        if app.state.device_monitor:
            await app.state.device_monitor.close()
        await app.state.tts.close()
        if app.state.mcp:
            await app.state.mcp.close()
        if app.state.model:
            await app.state.model.close()


app = FastAPI(title="Hubitat MCP AI v2", version="2.0.0-alpha.76", lifespan=lifecycle)
app.include_router(benchmark_router)
app.include_router(autonomous_router)
app.include_router(reasoning_router)
app.include_router(prospective_router)


@app.middleware("http")
async def prevent_stale_interface(request: Request, call_next):
    response = await call_next(request)
    # The HTML contains the API client. Never reuse it across add-on updates;
    # API responses can also contain private operational data.
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1500)


class AskRequest(BaseModel):
    request_id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID | None = None
    question: str = Field(min_length=1, max_length=10000)
    history: list[dict] = Field(default_factory=list, max_length=20)


@app.get("/")
async def index():
    return FileResponse(Path(__file__).parent / "ui.html", media_type="text/html")


@app.get("/api/status")
async def status():
    options = app.state.options
    mcp: MCPClient | None = app.state.mcp
    return {
        "version": app.version,
        "mode": "native-model-led-mcp",
        "configured": bool(mcp and app.state.model and (
            str(options["model_base_url"]).rstrip("/") != "https://ollama.com"
            or bool(str(options["model_api_key"]).strip())
        )),
        "configuration_error": app.state.configuration_error,
        "model": str(options["model_name"]),
        "recorder": app.state.recorder.status(),
        "device_monitor": {
            "enabled": bool(options.get("device_monitor_enabled", False)),
            "configured": getattr(app.state, "device_monitor", None) is not None,
            "configuration_error": getattr(app.state, "device_monitor_error", None),
            "read_only": True,
        },
        "tts": app.state.tts.status(),
    }


def require_ui_request(request: Request):
    # Same-origin UI fetches carry this header; cross-origin scripts need a
    # CORS preflight, which this app does not enable. Forms cannot supply it.
    if request.headers.get("x-homebrain-request") != "1":
        raise HTTPException(403, "Interface is out of date or the request header is missing. Close and reopen the v2 interface, then refresh the page. API clients must send X-Homebrain-Request: 1")



@app.get("/api/overview")
async def overview(request: Request):
    """One bounded read-only native inventory snapshot; no model or writes."""
    require_ui_request(request)
    mcp = getattr(app.state, "mcp", None)
    if mcp is None:
        return {"available": False, "read_only": True,
                "reason": "Native Hubitat MCP is not configured"}
    try:
        snapshot = await asyncio.wait_for(read_overview(mcp), timeout=12)
    except (MCPError, OverviewUnavailable, ValueError, asyncio.TimeoutError):
        # Do not leak upstream error details, tool response text, secrets,
        # private device lists, or private connection URLs to browser errors.
        return {"available": False, "read_only": True,
                "reason": "Read-only inventory unavailable; verify MCP connectivity and inventory permissions"}
    return {"available": True, **snapshot}


@app.get("/api/sources/device-monitor/check")
async def check_device_monitor(request: Request):
    """Explicit, one-shot, read-only connectivity check; never return tokens."""
    require_ui_request(request)
    monitor = getattr(app.state, "device_monitor", None)
    if monitor is None:
        return {
            "configured": False, "reachable": False,
            "error": "Optional Hub & Device Monitor connection is not configured",
        }
    try:
        result = await asyncio.wait_for(monitor.query({"mode": "status"}), timeout=10)
    except (ValueError, asyncio.TimeoutError):
        # Do not expose backend URLs, tokens or arbitrary downstream text.
        return {"configured": True, "reachable": False,
                "error": "Read-only monitor status query failed; check LAN reachability and app OAuth"}
    selected = result.get("selected_devices")
    if not isinstance(selected, list):
        return {"configured": True, "reachable": False,
                "error": "Monitor returned invalid selected-device inventory"}
    return {
        "configured": True, "reachable": True, "read_only": True,
        "monitor_version": result.get("monitor_version"),
        "monitor_observed_at_utc": result.get("monitor_observed_at_utc"),
        "selected_devices": len(selected),
        "selected_power_capable_devices": sum(
            1 for x in selected if isinstance(x, dict) and x.get("has_power") is True
        ),
        "historical_sample_coverage_verified": False,
        "note": "Reachability/status do not establish whether any device has saved measurements in the requested time interval.",
    }


@app.post("/api/tts")
async def speak_tts(payload: TTSRequest, request: Request):
    """Explicit answer playback through configured HA companion notify service."""
    require_ui_request(request)
    try:
        return {"success": True, **(await app.state.tts.speak(payload.text))}
    except HomeAssistantTTSConfigurationError as exc:
        raise HTTPException(409, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except Exception as exc:
        # Do not echo downstream HA errors containing private data or tokens.
        raise HTTPException(502, "Home Assistant mobile TTS delivery failed") from exc


@app.post("/api/tts/stop")
async def stop_tts(request: Request):
    require_ui_request(request)
    try:
        return {"success": True, **(await app.state.tts.stop())}
    except HomeAssistantTTSConfigurationError as exc:
        raise HTTPException(409, str(exc)) from None
    except Exception as exc:
        raise HTTPException(502, "Home Assistant mobile TTS stop failed") from exc


@app.get("/api/activity/{request_id}")
async def activity(request_id: UUID):
    interaction = app.state.interactions.get(str(request_id))
    return interaction.status() if interaction else {"current": None, "pending": None}


class ClearConversation(BaseModel):
    conversation_id: UUID


@app.post("/api/conversation/clear")
async def clear_conversation(request: ClearConversation, http_request: Request):
    require_ui_request(http_request)
    app.state.conversations.clear(str(request.conversation_id))
    return {"cleared": True}


class Confirmation(BaseModel):
    id: UUID
    approved: StrictBool


@app.post("/api/activity/{request_id}/confirm")
async def confirm(request_id: UUID, decision: Confirmation, http_request: Request):
    require_ui_request(http_request)
    interaction = app.state.interactions.get(str(request_id))
    if interaction is None:
        raise HTTPException(409, "This request is no longer active")
    try:
        interaction.decide(str(decision.id), decision.approved)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    return {"accepted": True}


@app.post("/api/ask")
async def ask(request: AskRequest, http_request: Request):
    require_ui_request(http_request)
    if app.state.configuration_error:
        raise HTTPException(503, app.state.configuration_error)
    if (str(app.state.options["model_base_url"]).rstrip("/") == "https://ollama.com"
            and not str(app.state.options["model_api_key"]).strip()):
        raise HTTPException(503, "Configure the Ollama Cloud API key in add-on options")
    if app.state.mcp is None or app.state.model is None:
        raise HTTPException(503, "Configure the model and Hubitat MCP URL in add-on options")
    request_id = str(request.request_id)
    if request_id in app.state.interactions:
        raise HTTPException(409, "This request is already active")
    interaction = Interaction()
    app.state.interactions[request_id] = interaction
    try:
        async with app.state.ask_lock:
            try:
                prior, prior_count = (
                    app.state.conversations.context(str(request.conversation_id))
                    if request.conversation_id else ("", 0)
                )
                indexed = (app.state.conversations.source_count(str(request.conversation_id))
                           if request.conversation_id else 0)
                # Only server-held redacted receipts are exposed, scoped by UUID.
                def read_prior(receipt_id, offset=0, max_chars=12000):
                    return app.state.conversations.read_receipt(
                        str(request.conversation_id), receipt_id, offset, max_chars
                    )
                # Do not alter the existing Ask call signature when the
                # optional historian is absent (including test-model shims).
                monitor_kwargs = (
                    {"device_monitor": app.state.device_monitor}
                    if getattr(app.state, "device_monitor", None) is not None
                    else {}
                )
                result = await app.state.model.answer(
                    request.question, request.history,
                    app.state.mcp, int(app.state.options["investigation_timeout_seconds"]),
                    before_call=interaction.before_call,
                    prior_evidence=prior, prior_receipts=prior_count,
                    prior_reader=read_prior if request.conversation_id and indexed else None,
                    **monitor_kwargs,
                )
                result["prior_sources_indexed"] = indexed
                result["prior_evidence_reads"] = sum(
                    item.get("result_kind") == "prior_evidence_read"
                    for item in result.get("tool_calls", [])
                    if isinstance(item, dict)
                )
                if request.conversation_id and result.get("tool_calls"):
                    app.state.conversations.record(
                        str(request.conversation_id), request.question, result["tool_calls"]
                    )
                return result
            except MCPError as exc:
                return {"success": False, "answer": f"MCP connection failure: {exc}",
                        "tool_calls": [], "error": "mcp"}
            except RuntimeError as exc:
                return {"success": False, "answer": f"Model/transport failure: {exc}",
                        "tool_calls": [], "error": "model"}
    finally:
        app.state.interactions.pop(request_id, None)



class EvaluationReplayRequest(BaseModel):
    capture: dict
    send_private_evidence_to_configured_model: StrictBool = False


@app.post("/api/evaluation/replay")
async def evaluation_replay(payload: EvaluationReplayRequest, http_request: Request):
    """Optional private, tool-free replay. No disk writes, MCP calls or history."""
    require_ui_request(http_request)
    if payload.send_private_evidence_to_configured_model is not True:
        raise HTTPException(403, "Explicit model-data transmission consent required")
    model = app.state.model
    if model is None or app.state.configuration_error:
        raise HTTPException(503, "Configure the V2 model before using evaluation")
    if (str(app.state.options["model_base_url"]).rstrip("/") == "https://ollama.com"
            and not str(app.state.options["model_api_key"]).strip()):
        raise HTTPException(503, "Configure the Ollama Cloud API key first")
    try:
        frozen = freeze_capture(payload.capture)
    except FrozenEvaluationError as exc:
        raise HTTPException(422, str(exc)) from None
    # Share Ask's lock: no simultaneous normal assistant request or another
    # expensive three-round replay. The normal Ask answer path is untouched.
    async with app.state.ask_lock:
        try:
            return await replay_frozen_capture(
                model, frozen,
                timeout_seconds=int(app.state.options["investigation_timeout_seconds"]),
            )
        except FrozenEvaluationError as exc:
            raise HTTPException(422, str(exc)) from None
        except RuntimeError:
            # Provider errors may contain raw request fragments or credentials.
            raise HTTPException(502, "Configured model replay failed; no Hubitat operation ran") from None


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
