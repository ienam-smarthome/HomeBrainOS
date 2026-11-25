"""Standalone v2 Home Assistant ingress app: native model-MCP loop + external recorder."""
from __future__ import annotations

import asyncio
import json
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from benchmark import BenchmarkWorkspace
from benchmark_routes import router as benchmark_router
from autonomous_lab import AutonomousLab
from autonomous_routes import router as autonomous_router
from reasoning_experiment import ReasoningExperiment
from reasoning_routes import router as reasoning_router
from prospective_routes import router as prospective_router
from acceptance_routes import router as acceptance_router
from prospective_source_ab import ProspectiveWorkspace
from pydantic import BaseModel, Field, StrictBool

from model_routing import CloudAgent, probe_cloud_tool_call
from write_receipt_evidence import model_error_kind
from external_hub_diagnostics import ExternalHubDiagnostics
from device_monitor import HubDeviceMonitor
from home_overview import OverviewUnavailable, read_overview
from home_assistant_tts import HomeAssistantTTS, HomeAssistantTTSConfigurationError
from mcp import MCPError, MCPClient
from agent import Agent, InitialCatalogUnavailable
from interaction import Interaction
from routine_approval_policy import trusted_switch_ids
from one_off_cleanup import OneOffCleanup
from network_status import NetworkWatch, network_status
from home_knowledge import (STARTER_NOTES, BriefingSchedule, HomeWatch, HomeKnowledge, HomeNotes,
                            briefing_text)
from conversation import ConversationEvidence
from frozen_evaluation import FrozenEvaluationError, freeze_capture, replay_frozen_capture


DEFAULTS: dict[str, Any] = {
    "hubitat_mcp_url": "",
    "hubitat_mcp_token": "",
    "network_router_host": "",
    "cloud_mode": "free",
    "cloud_free_model": "openrouter/free",
    "cloud_paid_provider": "openrouter",
    "cloud_paid_model": "google/gemini-3.1-flash-lite",
    "ollama_cloud_model": "nemotron-3-super",
    "cloud_paid_consent": False,
    "cloud_api_key": "",
    "ollama_cloud_api_key": "",
    "model_timeout_seconds": 120,
    "mcp_timeout_seconds": 25,
    "investigation_timeout_seconds": 300,
    # This personal V2 deployment treats a new explicit Ask as consent ONLY
    # for source-verified ordinary lights. Generic switches need an explicit
    # native-ID allowlist; all sensitive actions retain approval.
    "routine_auto_approve_lights": True,
    "routine_auto_approve_safe_switch_ids": "",
    "routine_auto_approve_internet_block": True,
    "hub_timezone": "Europe/London",
    "external_hub_diagnostics_enabled": False,
    "external_hub_diagnostics_hub_url": "",
    "external_hub_diagnostics_probe_seconds": 30,
    "external_hub_diagnostics_cpu_cores": 4,
    "external_hub_diagnostics_hub_timezone": "Europe/London",
    "external_hub_diagnostics_retention_days": 30,
    "device_monitor_enabled": False,
    "device_monitor_api_base": "",
    "device_monitor_access_token": "",
    "one_off_cleanup_enabled": False,
    "one_off_cleanup_dry_run": True,
    "one_off_cleanup_time": "07:00",
    "one_off_cleanup_timezone": "Europe/London",
    "one_off_cleanup_grace_minutes": 15,
    "ha_tts_enabled": False,
    "ha_tts_notify_service": "",
    "ha_tts_media_stream": "",
    "briefing_enabled": False,
    "briefing_time": "07:30",
    "home_alerts_enabled": False,
    "home_alert_open_minutes": 30,
    "network_alerts_enabled": False,
    "network_alert_notify_service": "",
    "network_alert_grace_minutes": 5,
    "network_alert_hub_grace_minutes": 8,
}


def config(path: Path = Path("/data/options.json")) -> dict:
    result = dict(DEFAULTS)
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(saved, dict):
            raise ValueError("Invalid add-on options")
        result.update({key: saved[key] for key in DEFAULTS if key in saved})
    return result


@asynccontextmanager
async def lifecycle(app: FastAPI):
    options = config()
    app.state.options = options
    app.state.ask_lock = asyncio.Lock()
    app.state.interactions = {}
    app.state.ask_tasks = {}
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
    app.state.alert_push = HomeAssistantTTS(
        enabled=True,
        supervisor_token=str(os.getenv("SUPERVISOR_TOKEN") or os.getenv("HASSIO_TOKEN") or ""),
        notify_service=str(options["network_alert_notify_service"] or options["ha_tts_notify_service"]),
    )

    async def _probe_network():
        return await network_status(str(options.get("hubitat_mcp_url", "")),
                                    str(options.get("network_router_host", "")))

    app.state.network_watch = NetworkWatch(
        _probe_network, app.state.alert_push.push,
        grace={"internet": max(1, int(options["network_alert_grace_minutes"])) * 60,
               "hub": max(1, int(options["network_alert_hub_grace_minutes"])) * 60},
        enabled=bool(options["network_alerts_enabled"]))
    app.state.network_watch.start()
    try:
        app.state.model = CloudAgent(
            mode=str(options["cloud_mode"]),
            free_model=str(options["cloud_free_model"]),
            paid_model=str(options["cloud_paid_model"]),
            paid_provider=str(options["cloud_paid_provider"]),
            ollama_model=str(options["ollama_cloud_model"]),
            paid_consent=options["cloud_paid_consent"],
            api_key=str(options["cloud_api_key"]),
            ollama_api_key=str(options["ollama_cloud_api_key"]),
            model_timeout=int(options["model_timeout_seconds"]),
            cpu_cores=int(options["external_hub_diagnostics_cpu_cores"]),
        )
        app.state.model.hub_timezone = str(options["hub_timezone"])
    except ValueError as exc:
        app.state.configuration_error = str(exc)
    # Model key/config must not disable independent read-only System Health.
    try:
        if str(options["hubitat_mcp_url"]).strip():
            app.state.mcp = MCPClient(
                str(options["hubitat_mcp_url"]),
                str(options["hubitat_mcp_token"]),
                int(options["mcp_timeout_seconds"]),
            )
    except (MCPError, ValueError) as exc:
        app.state.configuration_error = str(exc)
    async def _read_snapshot():
        if app.state.mcp is None:
            raise RuntimeError("MCP not configured")
        return await asyncio.wait_for(read_overview(app.state.mcp), timeout=25)

    app.state.home_knowledge = HomeKnowledge(
        HomeNotes(Path("/data/homebrain-v2-home-notes.txt")), _read_snapshot)
    if app.state.model is not None:
        app.state.model.home_context = app.state.home_knowledge.context

    async def _build_briefing():
        snapshot = await app.state.home_knowledge.refresh(force=True)
        if snapshot is None:
            raise RuntimeError("inventory unavailable")
        failing = app.state.network_watch.status().get("failing", {})
        problems = {k: f"{k} unreachable for about {round(v / 60)} min" for k, v in failing.items()}
        zone = ZoneInfo(str(options["hub_timezone"]))
        return briefing_text(snapshot, problems=problems, local_now=datetime.now(zone))

    async def _send_briefing(title, body):
        await app.state.alert_push.push(title, body)

    app.state.briefing = None
    try:
        if options["briefing_enabled"]:
            app.state.briefing = BriefingSchedule(
                _build_briefing, _send_briefing, time_of_day=str(options["briefing_time"]),
                timezone=str(options["hub_timezone"]))
            app.state.briefing.start()
    except (ValueError, KeyError) as exc:
        app.state.configuration_error = f"briefing: {exc}"
    app.state._build_briefing = _build_briefing

    async def _read_home_snapshot():
        return await app.state.home_knowledge.refresh(force=True)

    app.state.home_watch = HomeWatch(
        _read_home_snapshot, app.state.alert_push.push,
        grace={"contact": max(1, int(options["home_alert_open_minutes"])) * 60},
        enabled=bool(options["home_alerts_enabled"]))
    app.state.home_watch.start()
    app.state.home_profile_task = asyncio.create_task(app.state.home_knowledge.refresh())
    app.state.one_off_cleanup = OneOffCleanup(
        app.state.mcp,
        enabled=bool(options["one_off_cleanup_enabled"]),
        dry_run=bool(options["one_off_cleanup_dry_run"]),
        daily_time=str(options["one_off_cleanup_time"]),
        timezone_name=str(options["one_off_cleanup_timezone"]),
        grace_minutes=int(options["one_off_cleanup_grace_minutes"]),
        state_file=Path("/data/homebrain-v2-one-off-cleanup.json"),
    )
    app.state.one_off_cleanup.start()
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
        await app.state.one_off_cleanup.close()
        await app.state.recorder.close()
        if app.state.device_monitor:
            await app.state.device_monitor.close()
        await app.state.tts.close()
        await app.state.network_watch.close()
        if app.state.briefing:
            await app.state.briefing.close()
        await app.state.home_watch.close()
        app.state.home_profile_task.cancel()
        await app.state.alert_push.close()
        if app.state.mcp:
            await app.state.mcp.close()
        if app.state.model:
            await app.state.model.close()


app = FastAPI(title="Hubitat MCP AI v2", version="2.0.0-alpha.198", lifespan=lifecycle)
app.include_router(benchmark_router)
app.include_router(autonomous_router)
app.include_router(reasoning_router)
app.include_router(prospective_router)
app.include_router(acceptance_router)


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
    prepare_action: bool = False  # explicitly selected new retry; NOT write consent
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
        "configured": bool(mcp and app.state.model and
                           not app.state.configuration_error),
        "configuration_error": app.state.configuration_error,
        "model": (app.state.model.model if app.state.model else
                  str(options.get("cloud_free_model", "openrouter/free")
                      if options.get("cloud_mode", "free") == "free"
                      else options.get("ollama_cloud_model", "nemotron-3-super")
                      if options.get("cloud_paid_provider", "openrouter") == "ollama"
                      else options.get("cloud_paid_model",
                                       "google/gemini-3.1-flash-lite"))),
        "model_routing": (app.state.model.route_status()
                          if hasattr(app.state.model, "route_status") else None),
        "recorder": app.state.recorder.status(),
        "routine_native_authorization": {
            "ordinary_lights_enabled": options.get("routine_auto_approve_lights") is True,
            "explicitly_trusted_switch_count": len(trusted_switch_ids(str(
                options.get("routine_auto_approve_safe_switch_ids", "")
            ))),
            "sensitive_writes_still_require_confirmation": True,
            "original_ask_only": True,
        },
        "device_monitor": {
            "enabled": bool(options.get("device_monitor_enabled", False)),
            "configured": getattr(app.state, "device_monitor", None) is not None,
            "configuration_error": getattr(app.state, "device_monitor_error", None),
            "read_only": True,
        },
        "tts": app.state.tts.status(),
        "one_off_cleanup": app.state.one_off_cleanup.status(),
    }



@app.post("/api/model/probe")
async def model_probe(request: Request):
    """Explicit model-only fixture tool-call check; zero native MCP access."""
    require_ui_request(request)
    model = getattr(app.state, "model", None)
    if model is None or app.state.configuration_error:
        raise HTTPException(503, "Configure cloud inference and OpenRouter API key first")
    try:
        return await asyncio.wait_for(probe_cloud_tool_call(model), timeout=65)
    except (RuntimeError, ValueError, asyncio.TimeoutError) as exc:
        # Never forward provider message/body that may include private data.
        raise HTTPException(502, "Cloud test failed: " + (
            str(exc) if isinstance(exc, RuntimeError) else "model response invalid"
        )) from None


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
        snapshot = await asyncio.wait_for(read_overview(mcp), timeout=20)
    except (MCPError, OverviewUnavailable, ValueError, asyncio.TimeoutError):
        # Do not leak upstream error details, tool response text, secrets,
        # private device lists, or private connection URLs to browser errors.
        return {"available": False, "read_only": True,
                "reason": "Read-only inventory unavailable; verify MCP connectivity and inventory permissions"}
    return {"available": True, **snapshot}


@app.get("/api/network/status")
async def network(request: Request):
    """One bounded, read-only reachability probe set; no model calls or writes."""
    require_ui_request(request)
    options = app.state.options
    return await network_status(str(options.get("hubitat_mcp_url", "")),
                                str(options.get("network_router_host", "")))


@app.get("/api/home-notes")
async def home_notes_get(request: Request):
    require_ui_request(request)
    saved = app.state.home_knowledge.notes.load()
    return {"notes": saved, "starter": STARTER_NOTES, "max_chars": 3000,
            "profile_available": bool(app.state.home_knowledge.snapshot)}


@app.put("/api/home-notes")
async def home_notes_put(request: Request):
    require_ui_request(request)
    body = await request.json()
    try:
        saved = app.state.home_knowledge.notes.save(body.get("notes"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"notes": saved, "saved": True}


@app.get("/api/home/alerts")
async def home_alerts(request: Request):
    return app.state.home_watch.status()


@app.get("/api/briefing")
async def briefing(request: Request):
    """On-demand briefing from one read-only inventory snapshot; no model, no writes."""
    require_ui_request(request)
    try:
        title, body = await app.state._build_briefing()
    except Exception:
        return {"available": False, "reason": "Inventory unavailable for the briefing"}
    sched = app.state.briefing
    return {"available": True, "title": title, "body": body,
            "scheduled": bool(sched), "last_error": sched.last_error if sched else None}


@app.get("/api/network/alerts")
async def network_alerts(request: Request):
    require_ui_request(request)
    return app.state.network_watch.status()


@app.post("/api/network/alerts/test")
async def network_alert_test(request: Request):
    """Sends one clearly labelled test push so the notify service can be verified."""
    require_ui_request(request)
    try:
        return await app.state.alert_push.push(
            "HomeBrainOS: test alert", "Network alerts are set up. This is only a test.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


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


@app.post("/api/activity/{request_id}/cancel")
async def cancel_active_ask(request_id: UUID, http_request: Request):
    """Cancel only this live Ask; never approve or replay an earlier action."""
    require_ui_request(http_request)
    key = str(request_id)
    interaction = app.state.interactions.get(key)
    task = getattr(app.state, "ask_tasks", {}).get(key)
    if interaction is None or task is None or task.done():
        return {"cancelled": False, "reason": "request_not_active",
                "native_write_outcome_unknown": False}
    # Invalidate the gate BEFORE cancellation; a late Approve cannot race
    # into an old chat after a new Speak/Ask has been submitted.
    interaction.invalidate()
    possibly_submitted = interaction.native_write_submission_started
    task.cancel()
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=3.0)
    except (asyncio.CancelledError, asyncio.TimeoutError):
        pass
    # No physical rollback is implied: an already-sent native operation
    # may still complete at Hubitat even though the browser request ended.
    return {"cancelled": True,
            "native_write_outcome_unknown": bool(possibly_submitted)}


@app.post("/api/ask")
async def ask(request: AskRequest, http_request: Request):
    require_ui_request(http_request)
    if app.state.configuration_error:
        raise HTTPException(503, app.state.configuration_error)
    if app.state.mcp is None or app.state.model is None:
        raise HTTPException(503, "Configure the model and Hubitat MCP URL in add-on options")
    request_id = str(request.request_id)
    if request_id in app.state.interactions:
        raise HTTPException(409, "This request is already active")
    # Every native write still goes through the per-request gate. The original
    # Ask may replace a second click ONLY for a single fresh source-verified
    # benign routine writer, never for broad or sensitive native operations.
    interaction = Interaction(
        require_native_write_approval=True,
        auto_approve_lights=app.state.options.get(
            "routine_auto_approve_lights") is True,
        trusted_safe_switch_ids=trusted_switch_ids(
            str(app.state.options.get("routine_auto_approve_safe_switch_ids", ""))
        ),
        auto_approve_internet_block=app.state.options.get(
            "routine_auto_approve_internet_block") is True,
    )
    app.state.interactions[request_id] = interaction
    request_task = asyncio.current_task()
    # Tests and embedding hosts may create the FastAPI app without its
    # lifespan; allocate the ephemeral task registry in that case too.
    if getattr(app.state, "ask_tasks", None) is None:
        app.state.ask_tasks = {}
    app.state.ask_tasks[request_id] = request_task
    try:
        interaction.set_phase("queued", detail="Waiting for the Ask slot")
        async with app.state.ask_lock:
            interaction.set_phase("catalog", detail="Checking connected native MCP catalog")
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
                    **({"enable_routine_bootstrap": True,
                        "enable_routine_post_write_readback": True}
                       if isinstance(app.state.model, Agent) else {}),
                    **({"prepare_action": True} if request.prepare_action else {}),
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
            except InitialCatalogUnavailable as exc:
                # An initial catalog failure means no model request or native
                # tool operation occurred. The provider account was not queried.
                # Report only a safe class/status, never an upstream error body,
                # credential-bearing URL, response headers or query parameters.
                detail = str(exc)
                match = re.fullmatch(r"MCP HTTP ([45][0-9]{2})", detail)
                status = int(match.group(1)) if match else None
                kind = ("http" if status is not None else
                        "timeout" if detail == "MCP timed out" else
                        "transport" if detail == "MCP transport failed" else
                        "catalog_error")
                safe_detail = (f"HTTP {status}" if status is not None else
                               "timeout" if kind == "timeout" else
                               "transport error" if kind == "transport" else
                               "catalog unavailable")
                return {
                    "success": False,
                    "answer": ("MCP catalog unavailable before investigation "
                               f"({safe_detail}). No model inference or native "
                               "domain read occurred. Retry manually after "
                               "checking the MCP service; no automatic retry "
                               "was made."),
                    "tool_calls": [], "rounds": 0, "error": "mcp",
                    "mcp_failure": {
                        "phase": "initial_catalog", "error_kind": kind,
                        "http_status": status, "model_invoked": False,
                        "native_domain_calls": 0, "automatic_retry": False,
                    },
                }
            except MCPError as exc:
                return {"success": False, "answer": f"MCP connection failure: {exc}",
                        "tool_calls": [], "error": "mcp"}
            except RuntimeError as exc:
                return {"success": False, "answer": f"Model/transport failure: {exc}",
                        "tool_calls": [], "error": "model",
                        "model_error_kind": model_error_kind(exc)}
    finally:
        app.state.interactions.pop(request_id, None)
        if app.state.ask_tasks.get(request_id) is request_task:
            app.state.ask_tasks.pop(request_id, None)



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
