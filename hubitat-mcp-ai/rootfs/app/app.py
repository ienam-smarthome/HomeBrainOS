from __future__ import annotations

import asyncio
import json
import hmac
import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Literal

import uvicorn
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field, model_validator

from api_response_builder import build_agent_response
from automation_ideas_service import suggest_new_automations
from automation_status_service import AutomationStatusService
from automation_diagnostic_policy import is_broad_automation_runtime_diagnostic
from device_read_contract import live_context_devices, live_context_is_complete
from device_state_summary import (
    active_non_light_switches,
    active_room_summary,
    device_attributes,
    is_light_device,
    room_name,
)
from health_audit_scheduler import MorningHealthScheduler
from historical_evidence_journal import HistoricalEvidenceJournal
from household_ollama_accounts import read_authorized_household_accounts
from health_audit_service import (
    HealthAuditService,
    is_comprehensive_system_audit_request,
    run_comprehensive_chat_audit,
)
from investigation_intelligence import plan_investigation, assess_investigation
from investigation_checkpoint import is_investigative_question
from causal_timeline import has_explicit_focal_clock
from composite_system_audit_policy import is_cross_domain_hub_audit_request
from targeted_rule_scope_policy import is_targeted_rule_investigation
from shared_investigation_completion import apply_shared_investigation_completion
from history_time_windows import (
    parse_history_window_request,
    reset_history_window_request,
    set_history_window_request,
)
from homebrain_agent import UnifiedMCPAgent
from adaptive_investigation_policy import model_led_investigation_request
from device_incident_depth import is_connectivity_root_cause_request
from rule_machine_analysis import historical_rule_execution_request, requires_rule_logic_inspection
from investigation_policy import is_causal_investigation, is_history_investigation
from mcp_agent_orchestrator import _explicit_mutation_request
from hub_timezone import HubTimezoneResolver
from home_assistant_tts import HomeAssistantTTS, HomeAssistantTTSConfigurationError
from groovy_source_investigation import requested_groovy_app_id
from investigation_objective import resolve_primary_objective
from ai_investigation_routing import (
    ReadRouteDecision, active_request_interpretation,
    decide_read_route, set_read_route, reset_read_route,
    explicit_system_check_command, explicit_whole_hub_report_request,
    explicit_aggregate_performance_request,
    set_request_interpretation, reset_request_interpretation,
)
from request_metrics import increment_active_metric
from mcp_client import HubitatMCPClient
from one_time_rule_cleanup import OneTimeRuleCleanupScheduler, OneTimeRuleCleanupService
from performance_api_finalizer import finalize_performance_api_outcome
from request_runtime import (
    RequestProgress, begin_progress, end_progress,
    set_request_stage, remember_verified_outcome, safe_partial_outcome,
    safe_receipt_partial_outcome,
    install_sensitive_log_redaction,
)
from performance_host_plan import (
    collect_broad_performance_outcome,
    is_broad_performance_request,
    is_whole_hub_optimization_request,
)
from provider_rate_limit_policy import describe_ollama_rate_limit
from chat_transport import PaidModelUnavailable
from anthropic_transport import describe_anthropic_http_error
from paid_model_routing import set_request_model_tier, reset_request_model_tier
from evidence_claim_calibrator import calibrate_api_outcome
from pushover_notifier import PushoverNotifier
from webui import render_page
from investigation_v2.test_webui import render_v2_test_page
from investigation_v2.browser_access import (
    COOKIE_NAME, COOKIE_AGE_SECONDS, mint_browser_access,
    verify_browser_access,
)
from investigation_v2.test_service import (
    match_verified_device_ids, require_test_access,
    resolve_verified_device_subjects, resolve_planned_device_subjects,
)
from investigation_v2.evaluate import evaluate_v2_with_model
from investigation_v2.intent_boundary import incompatible_v2_control_request
from investigation_v2.factual_objective import verified_factual_objective
from investigation_v2.replay_scorecard import replay_scorecard
from investigation_v2.temporal_scope import explicit_incident_window
from investigation_v2.semantic_plan import semantic_plan
from investigation_v2.role_enrichment import enrich_measurement_roles
from investigation_v2.semantic_execute import execute_inventory_plan, ground_named_inventory_plan
from investigation_v2.measurement_semantics import load_operator_meter_roles

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HomeBrainOS.App")
install_sensitive_log_redaction()

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
        "ollama_household_cloud_failover_enabled": False,
        "ollama_household_accounts_json": "[]",
        "ollama_cloud_first": False,
        "ollama_paid_routing_enabled": False,
        "ollama_paid_routing_mode": "hybrid",
        "ollama_paid_deep_model": "deepseek-v4-pro",
        "ollama_free_quota_paid_fallback_enabled": False,
        "anthropic_api_key": "",
        "anthropic_model": "claude-sonnet-4-6",
        "ollama_local_enabled": False,
        "ollama_local_base_url": "http://localhost:11434",
        "ollama_local_model": "",
        "ollama_local_timeout_seconds": 12,
        "ollama_local_connect_timeout_seconds": 3,
        "ollama_local_keep_alive_seconds": 120,
        "ollama_agent_timeout_seconds": 60,
        "investigation_deadline_seconds": 180,
        "performance_synthesis_timeout_seconds": 30,
        "stream_idle_timeout_seconds": 20,
        "mcp_timeout_seconds": 25,
        "mcp_device_cache_seconds": 12,
        "mcp_identity_cache_seconds": 120,
        "mcp_max_concurrent_calls": 2,
        "mcp_retry_attempts": 3,
        "mcp_retry_backoff_seconds": 0.25,
        "confirmation_ttl_seconds": 120,
        "unified_mcp_tool_limit": 48,
        "unified_mcp_max_tool_rounds": 9,
        "max_tool_result_chars": 24000,
        "require_sensitive_confirmation": True,
        "rule_write_enabled": True,
        # Rollback lever for the 0.10.410 reasoning-first refactor -- see
        # UnifiedMCPAgent.__init__'s docstring comment for the full
        # rationale. Default False: historical/causal/diagnostic READ
        # questions reason through the general model loop using the same
        # underlying tools instead of a hand-coded deterministic template.
        # Immediate device control, firmware install, and immediate
        # internet-access block/allow are writes and are never gated by
        # this flag. Set True to restore the exact prior all-deterministic
        # behaviour without a code change.
        "deterministic_reads_enabled": False,
        "causal_subject_prefetch_enabled": True,
        "historical_journal_enabled": False,
        "historical_journal_hub_url": "",
        "historical_journal_retention_days": 30,
        "historical_journal_max_rows": 100000,
        "historical_journal_capture_logs": False,
        "historical_journal_log_app_ids": "",
        "causal_deterministic_final_enabled": True,
        "causal_known_automations_json": "[{\"name\":\"Hallway Lights ON\",\"platform\":\"Aqara M3\",\"triggerMode\":\"any\",\"triggers\":[{\"device\":\"Hallway FP300\",\"aliases\":[\"Hallway FP300 sensor\"]},{\"device\":\"Hallway Aqara P1\",\"aliases\":[\"Hallway Sensor P1\"]}],\"derivedSensors\":[{\"device\":\"Hallway Soft Sensor\",\"kind\":\"occupancy\",\"sourceMode\":\"combined\",\"sources\":[{\"device\":\"Hallway FP300\",\"aliases\":[\"Hallway FP300 sensor\"]},{\"device\":\"Hallway Aqara P1\",\"aliases\":[\"Hallway Sensor P1\"]}]}],\"actions\":[{\"device\":\"Hallway Light 1\",\"transition\":\"on\"},{\"device\":\"Hallway Light 2\",\"transition\":\"on\"}]}]",
        "general_task_engine_enabled": False,
        "semantic_agent_enabled": True,
        "semantic_default_brightness_step": 20,
        "semantic_default_temperature_step": 1.0,
        "internet_control_aliases_json": "{}",
        "morning_health_check_enabled": True,
        "morning_health_check_time": "07:00",
        "one_time_rule_cleanup_enabled": True,
        "one_time_rule_cleanup_time": "01:00",
        "one_time_rule_cleanup_grace_minutes": 10,
        "health_check_log_hours": 24,
        "sensecap_d1_intentionally_powered_off": False,
        "comprehensive_audit_ai_analysis_enabled": True,
        "automation_diagnostic_ai_analysis_enabled": True,
        "health_check_low_battery": 20,
        "health_check_stale_hours": 24,
        "health_check_long_stale_hours": 168,
        "health_check_cluster_minutes": 15,
        "health_check_motion_active_hours": 2,
        "pushover_enabled": False,
        "pushover_app_token": "",
        "pushover_user_key": "",
        "pushover_device": "",
        "ha_tts_enabled": True,
        "ha_tts_notify_service": "",
        "ha_tts_media_stream": "",
        "investigation_v2_testing_enabled": False,
        "investigation_v2_test_token": "",
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
historical_journal = HistoricalEvidenceJournal(
    enabled=_bool(OPTIONS.get("historical_journal_enabled")),
    hub_url=str(OPTIONS.get("historical_journal_hub_url") or ""),
    path=Path(os.getenv("HISTORICAL_JOURNAL_PATH", "/data/homebrain-evidence-journal.sqlite3")),
    retention_days=int(OPTIONS.get("historical_journal_retention_days") or 30),
    max_rows=int(OPTIONS.get("historical_journal_max_rows") or 100000),
    capture_logs=_bool(OPTIONS.get("historical_journal_capture_logs")),
    log_app_ids=str(OPTIONS.get("historical_journal_log_app_ids") or ""),
)
mcp = HubitatMCPClient(
    endpoint_url=str(OPTIONS.get("hubitat_mcp_url") or ""),
    access_token=str(OPTIONS.get("hubitat_mcp_token") or ""),
    timeout_seconds=float(OPTIONS.get("mcp_timeout_seconds") or 25),
    device_cache_seconds=float(OPTIONS.get("mcp_device_cache_seconds") or 12),
    identity_cache_seconds=float(
        OPTIONS.get("mcp_identity_cache_seconds") or 120
    ),
    max_concurrent_calls=int(OPTIONS.get("mcp_max_concurrent_calls") or 2),
    retry_attempts=int(OPTIONS.get("mcp_retry_attempts") or 3),
    retry_backoff_seconds=float(
        OPTIONS.get("mcp_retry_backoff_seconds") or 0.25
    ),
)
automation_status = AutomationStatusService(mcp)
health_audit = HealthAuditService(
    mcp,
    automation_status,
    snapshot_path=Path(
        os.getenv("HEALTH_AUDIT_PATH", "/data/homebrain-health-audit.json")
    ),
    low_battery_threshold=int(OPTIONS.get("health_check_low_battery") or 20),
    log_hours=int(OPTIONS.get("health_check_log_hours") or 24),
    stale_hours=int(OPTIONS.get("health_check_stale_hours") or 24),
    long_stale_hours=int(OPTIONS.get("health_check_long_stale_hours") or 168),
    cluster_minutes=int(OPTIONS.get("health_check_cluster_minutes") or 15),
    motion_active_hours=int(OPTIONS.get("health_check_motion_active_hours") or 2),
)
# Explicit add-on setting supplied by the user; never infer physical power
# status from repeated transport errors, and never persist this as an MCP fact.
health_audit.sensecap_d1_intentionally_powered_off = _bool(
    OPTIONS.get("sensecap_d1_intentionally_powered_off"), False
)
pushover_notifier = PushoverNotifier(
    enabled=_bool(OPTIONS.get("pushover_enabled"), False),
    app_token=str(OPTIONS.get("pushover_app_token") or ""),
    user_key=str(OPTIONS.get("pushover_user_key") or ""),
    device=str(OPTIONS.get("pushover_device") or ""),
)
home_assistant_tts = HomeAssistantTTS(
    enabled=_bool(OPTIONS.get("ha_tts_enabled"), True),
    supervisor_token=str(os.getenv("SUPERVISOR_TOKEN") or os.getenv("HASSIO_TOKEN") or ""),
    notify_service=str(OPTIONS.get("ha_tts_notify_service") or ""),
    media_stream=str(OPTIONS.get("ha_tts_media_stream") or ""),
)


def _ignore_scheduler_evidence(*_args: Any, **_kwargs: Any) -> None:
    return None


_health_timezone = HubTimezoneResolver(
    mcp,
    _ignore_scheduler_evidence,
)


async def _health_scheduler_now() -> datetime:
    now, _name, _source = await _health_timezone.now_in_hub_timezone(
        lambda: datetime.now(timezone.utc)
    )
    return now


health_scheduler = MorningHealthScheduler(
    health_audit,
    enabled=_bool(OPTIONS.get("morning_health_check_enabled"), True),
    daily_time=str(OPTIONS.get("morning_health_check_time") or "07:00"),
    local_now=_health_scheduler_now,
    notifier=pushover_notifier,
)
one_time_rule_cleanup = OneTimeRuleCleanupService(
    mcp,
    local_now=_health_scheduler_now,
    grace_minutes=int(OPTIONS.get("one_time_rule_cleanup_grace_minutes") or 10),
)
one_time_rule_cleanup_scheduler = OneTimeRuleCleanupScheduler(
    one_time_rule_cleanup,
    enabled=_bool(OPTIONS.get("one_time_rule_cleanup_enabled"), True),
    daily_time=str(OPTIONS.get("one_time_rule_cleanup_time") or "01:00"),
    local_now=_health_scheduler_now,
    state_path=Path(
        os.getenv(
            "ONE_TIME_RULE_CLEANUP_STATE_PATH",
            "/data/homebrain-one-time-rule-cleanup.json",
        )
    ),
)

agent = UnifiedMCPAgent(
    mcp_client=mcp,
    api_key=str(OPTIONS.get("ollama_direct_cloud_api_key") or ""),
    model_name=str(
        OPTIONS.get("ollama_direct_cloud_model")
        or OPTIONS.get("ollama_cloud_model")
        or "gemma4:31b-cloud"
    ),
    base_url=str(OPTIONS.get("ollama_direct_cloud_base_url") or "https://ollama.com"),
    household_cloud_accounts=read_authorized_household_accounts(
        str(OPTIONS.get("ollama_household_accounts_json") or "[]"),
        enabled=_bool(OPTIONS.get("ollama_household_cloud_failover_enabled"), False),
    ),
    household_cloud_failover_enabled=_bool(
        OPTIONS.get("ollama_household_cloud_failover_enabled"), False
    ),
    cloud_first=_bool(OPTIONS.get("ollama_cloud_first"), False),
    paid_routing_enabled=_bool(OPTIONS.get("ollama_paid_routing_enabled"), False),
    paid_routing_mode=str(OPTIONS.get("ollama_paid_routing_mode") or "hybrid"),
    paid_budget_usd=None,  # no HomeBrain budget; provider credit settings apply
    paid_deep_model=str(OPTIONS.get("ollama_paid_deep_model") or "deepseek-v4-pro"),
    free_quota_paid_fallback_enabled=_bool(OPTIONS.get("ollama_free_quota_paid_fallback_enabled"), False),
    claude_api_key=str(OPTIONS.get("anthropic_api_key") or ""),
    claude_model=str(OPTIONS.get("anthropic_model") or "claude-sonnet-4-6"),
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
    rule_write_enabled=_bool(OPTIONS.get("rule_write_enabled"), True),
    deterministic_reads_enabled=_bool(
        OPTIONS.get("deterministic_reads_enabled"), False
    ),
    causal_subject_prefetch_enabled=_bool(
        OPTIONS.get("causal_subject_prefetch_enabled"), True
    ),
    causal_deterministic_final_enabled=_bool(
        OPTIONS.get("causal_deterministic_final_enabled"), True
    ),
    known_automations=OPTIONS.get("causal_known_automations_json"),
    internet_control_aliases=OPTIONS.get("internet_control_aliases_json"),
    general_task_engine_enabled=_bool(
        OPTIONS.get("general_task_engine_enabled"), False
    ),
    semantic_agent_enabled=_bool(
        OPTIONS.get("semantic_agent_enabled"), True
    ),
    semantic_default_brightness_step=int(
        OPTIONS.get("semantic_default_brightness_step") or 20
    ),
    semantic_default_temperature_step=float(
        OPTIONS.get("semantic_default_temperature_step") or 1.0
    ),
)
agent.performance_synthesis_timeout_seconds = float(
    OPTIONS.get("performance_synthesis_timeout_seconds") or 30
)
# Read-only journal evidence is optional; do not affect ordinary MCP requests.
agent.historical_journal = historical_journal
# Persist safe source-stamped command/state rows encountered in native read-only
# MCP history queries; the collector remains opt-in and never performs writes.
agent.executor.historical_journal = historical_journal


class RequestCoordinator:
    """Own in-flight agent tasks so supersede and disconnect cancel backend work."""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._lock = asyncio.Lock()
        self._progress: dict[str, RequestProgress] = {}

    def progress(self, key: str, request_id: str) -> dict[str, Any]:
        state = self._progress.get(key)
        if state is None or state.request_id != request_id:
            return {"stage": "Waiting for request", "completed": False}
        return state.public()

    async def run(
        self,
        key: str,
        operation: Awaitable[Any],
        *,
        connection: Request | None = None,
        request_id: str = "",
        deadline_seconds: float | None = None,
    ) -> Any:
        progress = RequestProgress(request_id=request_id or uuid.uuid4().hex)

        async def tracked() -> Any:
            token = begin_progress(progress)
            try:
                return await operation
            finally:
                end_progress(token)

        task = asyncio.create_task(tracked(), name=f"homebrain-request:{key}")
        async with self._lock:
            previous = self._tasks.get(key)
            self._tasks[key] = task
            self._progress[key] = progress

        if previous is not None and previous is not task and not previous.done():
            previous.cancel("superseded by a newer request")
            with suppress(asyncio.CancelledError, asyncio.TimeoutError):
                await asyncio.wait_for(previous, timeout=2.0)

        try:
            while True:
                done, _ = await asyncio.wait({task}, timeout=0.1)
                if task in done:
                    progress.completed = True
                    return task.result()
                if (deadline_seconds is not None and
                        time.monotonic() - progress.started >= deadline_seconds):
                    last_stage = progress.stage
                    progress.stage = "Investigation reached its time limit"
                    logger.warning(
                        "Investigation deadline: request_id=%s limit=%.1fs phase=%s "
                        "verified_reads=%d checkpoint=%s",
                        progress.request_id, deadline_seconds, last_stage,
                        len(progress.verified_reads), progress.checkpoint is not None,
                    )
                    task.cancel("investigation deadline exceeded")
                    with suppress(asyncio.CancelledError, asyncio.TimeoutError):
                        await asyncio.wait_for(task, timeout=2.0)
                    progress.completed = True
                    if progress.checkpoint is not None:
                        return safe_partial_outcome(
                            progress.checkpoint,
                            reason=f"{deadline_seconds:g}s time limit",
                            additional_reads=progress.verified_reads,
                        )
                    if progress.verified_reads:
                        return safe_receipt_partial_outcome(
                            progress.verified_reads,
                            reason=f"{deadline_seconds:g}s time limit",
                        )
                    raise HTTPException(
                        status_code=504,
                        detail=(
                            f"Investigation reached its {deadline_seconds:g}s deadline "
                            f"during {last_stage}. No verified read-only results "
                            "were available. Check the HomeBrain add-on Logs "
                            "using the request ID and review "
                            "investigation_deadline_seconds in the add-on settings."
                        ),
                    )
                if connection is not None and await connection.is_disconnected():
                    # A browser connection failure is NOT a native MCP write
                    # receipt or evidence that an earlier write was rolled back.
                    # Log a safe request ID for incident correlation, never
                    # user content or tokens. Do not auto retry the action.
                    logger.warning(
                        "Chat request disconnected; request_id=%s. "
                        "Any earlier Hubitat write outcome requires direct verification.",
                        progress.request_id,
                    )
                    progress.stage = "Cancelled: browser disconnected"
                    task.cancel("client disconnected")
                    with suppress(asyncio.CancelledError, asyncio.TimeoutError):
                        await asyncio.wait_for(task, timeout=2.0)
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
                    self._progress.pop(key, None)

    async def close(self) -> None:
        async with self._lock:
            tasks = list(self._tasks.values())
            self._tasks.clear()
            self._progress.clear()
        for task in tasks:
            if not task.done():
                task.cancel("application shutdown")
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task


request_coordinator = RequestCoordinator()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await historical_journal.start()
    health_scheduler.start()
    one_time_rule_cleanup_scheduler.start()
    try:
        yield
    finally:
        await historical_journal.close()
        await one_time_rule_cleanup_scheduler.close()
        await health_scheduler.close()
        await request_coordinator.close()
        await home_assistant_tts.close()
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


# Multi-stage Rule Machine design/creation requests routinely exceed 2,000 chars.
# Retain a finite input bound, but do not reject ordinary structured prompts.
MAX_CHAT_PROMPT_CHARS = 12000


class ChatRequest(BaseModel):
    prompt: str | None = Field(default=None, max_length=MAX_CHAT_PROMPT_CHARS)
    query: str | None = Field(default=None, max_length=MAX_CHAT_PROMPT_CHARS)
    history: list[HistoryItem] = Field(default_factory=list)
    session_id: str | None = Field(default=None, min_length=1, max_length=160)
    request_id: str | None = Field(default=None, min_length=1, max_length=160)
    model_tier: Literal["auto", "free", "paid", "claude"] = "free"

    @model_validator(mode="after")
    def require_message(self) -> "ChatRequest":
        value = (self.prompt or self.query or "").strip()
        if not value:
            raise ValueError("Prompt required")
        return self

    @model_validator(mode="after")
    def default_session_id(self) -> "ChatRequest":
        """Give every caller that omits session_id its own isolated key per request."""

        if not self.session_id:
            self.session_id = uuid.uuid4().hex
        return self

    @property
    def message(self) -> str:
        return (self.prompt or self.query or "").strip()

    @property
    def coordination_key(self) -> str:
        return self.session_id


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1500)


async def _creative_automation_recommendation() -> Any:
    """Advisory automations request that specifically wants NEW ideas."""

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


async def _agent_request(request: ChatRequest) -> Any:
    """Bind deterministic calendar semantics to this request's async context."""

    token = set_history_window_request(parse_history_window_request(request.message))
    route_token = None
    interpretation_token = None
    try:
        primary_objective = resolve_primary_objective(request.message)
        targeted_device = primary_objective.is_targeted_device
        broad_automation_diagnostic = is_broad_automation_runtime_diagnostic(
            request.message
        )
        cross_domain_audit = is_cross_domain_hub_audit_request(request.message)
        targeted_rule = is_targeted_rule_investigation(request.message)
        comprehensive_audit = (
            cross_domain_audit
            or is_comprehensive_system_audit_request(request.message)
        )
        broad_performance = is_broad_performance_request(request.message)
        # The legacy token classifiers are eligibility signals only. They
        # must NOT select the workflow when multiple read-only paths compete.
        # The free/selected model chooses scope in a single no-tools round;
        # malformed or timed-out choices fail open to the MCP reasoning loop.
        model_route = None
        candidate_fast_path = (
            comprehensive_audit or broad_automation_diagnostic
            or broad_performance
            or model_led_investigation_request(request.message)
            # Open-ended cause investigations should get ONE AI intent choice
            # even when legacy causal fast paths recognise similar words.
            # Exact-clock historical events preserve existing bounded reads.
            or (is_investigative_question(request.message)
                and not has_explicit_focal_clock(request.message))
            # A natural 'why is my device offline?' question may not contain
            # the old deep-investigation trigger words. It still needs one
            # AI-interpreted objective before any specialist can reclassify it.
            or is_connectivity_root_cause_request(request.message)
            # Rule-instance diagnostics should also let the AI decide what
            # the user is investigating; a lexical "rule" match must not
            # preempt their broader root-cause objective.
            or targeted_rule
        )
        if (candidate_fast_path
                and not primary_objective.is_source
                and not _explicit_mutation_request(request.message)):
            if (explicit_system_check_command(request.message)
                    or explicit_whole_hub_report_request(request.message)):
                model_route = "system_audit"
            elif explicit_aggregate_performance_request(request.message):
                model_route = "performance_report"
            else:
                # Ambiguous cases and explicitly negated report examples
                # reach the AI interpreter. Explicit whole-hub or aggregate
                # report commands retain their established fast read path.
                increment_active_metric("ai_read_route_arbitrated")
                set_request_stage("AI interpreting investigation scope")
                decision = await decide_read_route(
                    agent._chat, request.message,
                )
                model_route = (
                    "model_led" if (targeted_device or targeted_rule)
                    else decision.route
                )
                # Host scope overrides must not discard the already
                # interpreted goal. An old 'targeted device' classifier can
                # force model_led even when the first model suggested a broad
                # report; its broad objective is NOT allowed to leak into
                # subsequent app/tool/answer selection.
                active_decision = decision
                if model_route == "model_led" and decision.route != "model_led":
                    active_decision = ReadRouteDecision(
                        route="model_led", provenance="host_scope_override",
                        objective="general_investigation",
                        target=decision.target,
                        purpose=decision.purpose or request.message[:320],
                        answer_goal=decision.answer_goal,
                    )
                if active_decision.objective is not None:
                    interpretation_token = set_request_interpretation(
                        request.message, active_decision,
                    )
                if decision.provenance != "model_choice":
                    increment_active_metric("ai_read_route_fallback")
                increment_active_metric({
                    "model_led": "ai_read_route_model_led",
                    "system_audit": "ai_read_route_system_audit",
                    "performance_report": "ai_read_route_performance",
                }[model_route])
        if model_route is not None:
            route_token = set_read_route(model_route)

        if (model_route == "system_audit"
                and not targeted_device and not targeted_rule
                and not _explicit_mutation_request(request.message)):
            # Cross-domain and explicitly comprehensive audits use their own
            # tool-free AI opt-in, regardless of whether a broader automation
            # diagnostic phrase also matches. The latter should not silently
            # add a 12-second model timeout to a deterministic full-hub report.
            reasoned = (
                _bool(OPTIONS.get("comprehensive_audit_ai_analysis_enabled"), True)
                if comprehensive_audit else
                _bool(OPTIONS.get("automation_diagnostic_ai_analysis_enabled"), True)
            )
            if reasoned:
                if broad_automation_diagnostic and not comprehensive_audit:
                    return await run_comprehensive_chat_audit(
                        health_audit, mcp, analysis_chat=agent.transport.chat,
                        analysis_focus=request.message,
                    )
                return await run_comprehensive_chat_audit(
                    health_audit, mcp, analysis_chat=agent.transport.chat,
                    analysis_focus=request.message,
                )
            return await run_comprehensive_chat_audit(
                health_audit, mcp, ai_disabled_by_configuration=True,
            )
        if (not targeted_device and
                not _explicit_mutation_request(request.message) and
                (model_route == "performance_report" or
                 (model_route is None and broad_performance))):
            set_request_stage("Collecting Hubitat performance and scheduled jobs")
            outcome = await collect_broad_performance_outcome(agent, request.message)
            remember_verified_outcome(outcome)
            set_request_stage("Analysing scheduled jobs and evidence")
        else:
            set_request_stage("Gathering Hubitat MCP evidence")
            outcome = await agent.process_user_request_result(
                request.message,
                request.history,
                session_id=request.session_id,
            )
        if (interpretation_token is not None
                and hasattr(outcome, "interpreted_intent")):
            outcome.interpreted_intent = {
                "route": active_decision.route,
                "objective": active_decision.objective,
                "target": active_decision.target,
                "purpose": active_decision.purpose,
                "answer_goal": active_decision.answer_goal,
            }
        # A direct/specialized completion may have bypassed its own evidence
        # assessment. Preserve the original investigative goal at the API
        # boundary rather than disguising an incomplete read as an answer.
        goal = (
            None if primary_objective.is_source
            else plan_investigation(request.message)
        )
        if (
            goal is not None
            and getattr(outcome, "request_class", "") == "live-read"
            and getattr(outcome, "investigation_coverage", None) is None
            and hasattr(outcome, "investigation_coverage")
        ):
            outcome.investigation_coverage = assess_investigation(
                goal, list(getattr(outcome, "evidence", []) or [])
            )
        set_request_stage("Preparing evidence-based answer")
        if primary_objective.is_source or model_route == "model_led":
            # A successful source-led investigation may also sample app
            # performance. Do not send it through the separate performance
            # synthesizer, which can overwrite method-level reasoning with
            # a generic statistical answer (and spend another model round).
            # Shared source coverage and API evidence validation still run.
            return outcome
        return await finalize_performance_api_outcome(
            agent,
            mcp,
            outcome,
            request.message,
        )
    finally:
        if interpretation_token is not None:
            reset_request_interpretation(interpretation_token)
        if route_token is not None:
            reset_read_route(route_token)
        reset_history_window_request(token)


def _needs_investigation_deadline(prompt: str) -> bool:
    """Bound any genuine read-only investigation, not just system-wide audits.

    Keep conversational questions, current-state snapshots and all possible
    state-changing requests on their existing independent routes.
    """
    if _explicit_mutation_request(prompt):
        return False
    return bool(
        is_broad_performance_request(prompt)
        or is_cross_domain_hub_audit_request(prompt)
        or is_comprehensive_system_audit_request(prompt)
        or is_targeted_rule_investigation(prompt)
        or is_broad_automation_runtime_diagnostic(prompt)
        or model_led_investigation_request(prompt)
        or historical_rule_execution_request(prompt)
        or requested_groovy_app_id(prompt) is not None
        or is_causal_investigation(prompt)
        or is_history_investigation(prompt)
        or plan_investigation(prompt) is not None
    )


async def _answer_result(request: ChatRequest, connection: Request | None = None) -> Any:
    from scoped_app_status_read import scoped_status_app_id, read_scoped_app_status
    tier_token = set_request_model_tier(request.model_tier)
    try:
        operation: Awaitable[Any]
        scoped_id = scoped_status_app_id(request.message)
        if (scoped_id is not None
                and not requires_rule_logic_inspection(request.message)
                and not model_led_investigation_request(request.message)):
            operation = read_scoped_app_status(mcp, scoped_id)
        elif (
            automation_status.matches_request(request.message)
            and not requires_rule_logic_inspection(request.message)
            and requested_groovy_app_id(request.message) is None
            and plan_investigation(request.message) is None
            and not is_comprehensive_system_audit_request(request.message)
            and not is_cross_domain_hub_audit_request(request.message)
            and not is_broad_automation_runtime_diagnostic(request.message)
            and not is_whole_hub_optimization_request(request.message)
            and not model_led_investigation_request(request.message)
        ):
            if automation_status.is_advisory_request(
                request.message
            ) and automation_status.wants_new_automation_ideas(request.message):
                operation = _creative_automation_recommendation()
            else:
                if ("broken" in request.message.casefold() and
                        not automation_status.is_advisory_request(request.message)):
                    operation = automation_status.snapshot(brief=True)
                else:
                    operation = automation_status.snapshot(
                        advisory=automation_status.is_advisory_request(request.message)
                    )
        else:
            if (request.model_tier != "claude" and
                    not _bool(OPTIONS.get("ollama_direct_cloud_enabled"), True)):
                raise HTTPException(status_code=503, detail="Ollama Online is disabled")
            operation = _agent_request(request)
        outcome = await request_coordinator.run(
            request.coordination_key,
            operation,
            connection=connection,
            request_id=request.request_id or "",
            deadline_seconds=max(10.0, float(
                OPTIONS.get("investigation_deadline_seconds") or 180
            )) if _needs_investigation_deadline(request.message) else None,
        )
        # Single cross-route evidence assessment: even early host completions,
        # semantic fast paths and specialist routes pass this boundary before
        # /api/ask and /api/chat serialize their answer.
        # The agent call has ended, but final evidence calibration must
        # consume exactly the same AI objective, never re-interpret keywords.
        saved = getattr(outcome, "interpreted_intent", None)
        intent_token = None
        if isinstance(saved, dict) and isinstance(saved.get("objective"), str):
            intent_token = set_request_interpretation(
                request.message,
                ReadRouteDecision(
                    route=saved.get("route", "model_led"),
                    provenance="retained_request_interpretation",
                    objective=saved["objective"],
                    target=saved.get("target"),
                    purpose=saved.get("purpose"),
                ),
            )
        try:
            return calibrate_api_outcome(
                apply_shared_investigation_completion(outcome, request.message),
                request.message,
            )
        finally:
            if intent_token is not None:
                reset_request_interpretation(intent_token)
    except HTTPException:
        raise
    except PaidModelUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except asyncio.CancelledError:
        raise
    except httpx.HTTPStatusError as exc:
        if request.model_tier == "claude":
            status, detail, retry_after, error_type, category = (
                describe_anthropic_http_error(exc)
            )
            # Never log the exception itself: HTTP error bodies may contain
            # portions of a prompt, tool arguments or provider credentials.
            logger.warning(
                "Anthropic API HTTP %s; type=%s; category=%s",
                status, error_type, category,
            )
            raise HTTPException(
                status_code=status if status in {
                    400, 401, 402, 403, 404, 413, 429, 500, 502, 503, 504, 529,
                } else 502,
                detail=detail,
                headers={"Retry-After": retry_after} if retry_after else None,
            ) from None
        if request.model_tier == "paid" and exc.response.status_code == 402:
            raise HTTPException(
                status_code=402,
                detail="DeepSeek Pro could not continue: Ollama rejected paid "
                       "billing for this request. Check your Ollama account "
                       "credits or select Free. HomeBrain did not switch models.",
            ) from exc
        limited = describe_ollama_rate_limit(exc)
        if limited:
            detail, retry_after = limited
            # Return an actionable provider-status error, without provider
            # body, bearer token, or a misleading Hubitat/MCP failure.
            logger.warning("Ollama Cloud rate limit (HTTP 429); retry_after=%s", retry_after)
            raise HTTPException(
                status_code=429,
                detail=detail,
                headers={"Retry-After": retry_after} if retry_after else None,
            ) from exc
        # Ollama errors should be distinguishable from Anthropic errors too.
        # The Free selector is now the default; never instruct the user to
        # change provider without knowing which upstream service failed.
        # Avoid dumping the exception: provider error bodies are untrusted
        # and might include account or user evidence.
        ollama_status = exc.response.status_code
        ollama_errors = {
            400: "Ollama rejected the model request or tool/message format.",
            401: "Ollama Cloud authentication was rejected. Check the Ollama API key.",
            402: (
                "Ollama rejected free allowance or billing for this request."
                if request.model_tier == "free"
                else "Ollama account allowance or paid billing was rejected."
            ),
            403: "Ollama Cloud refused access to this model or API key.",
            404: "The requested Ollama model or API endpoint was not found.",
            413: "The Ollama request exceeded provider request limits.",
            500: "The Ollama model provider encountered an internal error.",
            502: "The Ollama model provider returned a gateway error.",
            503: "The Ollama model provider is temporarily unavailable.",
            504: "The Ollama model provider timed out.",
            529: "The Ollama model provider is overloaded.",
        }
        logger.warning("Ollama upstream HTTP status: %s", ollama_status)
        raise HTTPException(
            status_code=ollama_status if ollama_status in ollama_errors else 502,
            detail=(
                f"{ollama_errors.get(ollama_status, 'Ollama model request failed.')} "
                f"(Ollama HTTP {ollama_status})."
                + (" Free selection did not switch to a paid provider."
                   if request.model_tier == "free" else "")
            ),
        ) from None
    except Exception as exc:
        logger.exception("Unified MCP request failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        reset_request_model_tier(tier_token)


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
        "claude": {
            "configured": agent.transport.claude.configured,
            "model": agent.transport.claude.model,
            "provider": "Anthropic API",
            "billing": "Anthropic API account",
        },
        "paid_routing": {
            "enabled": agent.transport.paid_credit_guard.enabled,
            "mode": agent.transport.paid_credit_guard.mode,
            "model": agent.transport.paid_credit_guard.deep_model,
            "budget_policy": "ollama-account-only",
            "local_budget_enabled": False,
        },
        "tts": home_assistant_tts.status(),
        "one_time_rule_cleanup": one_time_rule_cleanup_scheduler.status(),
        "historical_journal": historical_journal.status(),
    }


@app.get("/api/status")
async def status() -> dict[str, Any]:
    return await health()

@app.get("/api/evidence-journal/status")
async def evidence_journal_status() -> dict[str, Any]:
    """Collection health, never a claim that historical coverage is complete."""
    return historical_journal.status()


@app.get("/api/evidence-journal/recent")
async def evidence_journal_recent(limit: int = 12) -> dict[str, Any]:
    """Recent non-log device observations; no private app message content."""
    if not historical_journal.enabled or not historical_journal._started:
        raise HTTPException(status_code=503, detail="Historical journal is not running")
    try:
        return await asyncio.to_thread(historical_journal.recent_events, limit)
    except (OSError, ValueError) as exc:
        logger.warning("Journal recent events unavailable: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Journal storage unavailable") from exc


@app.get("/api/evidence-journal/events")
async def evidence_journal_events(
    since: str, until: str, device_id: str = "", attribute: str = "",
    app_id: str = "", limit: int = 100, offset: int = 0,
) -> dict[str, Any]:
    """Bounded, read-only archived evidence; requires an exact device or app."""
    if not historical_journal.enabled or not historical_journal._started:
        raise HTTPException(status_code=503, detail="Historical journal is not running")
    try:
        return await asyncio.to_thread(
            historical_journal.query,
            since=since, until=until, device_id=device_id,
            attribute=attribute, app_id=app_id, limit=limit, offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/request-progress")
async def request_progress(session_id: str, request_id: str) -> dict[str, Any]:
    """Current progress only. No prompts, credentials or evidence in this endpoint."""
    return request_coordinator.progress(session_id, request_id)


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


async def _dashboard_devices() -> tuple[list[dict[str, Any]], str]:
    """Prefer the server's one-bulk-read live context for dashboard state.

    Older MCP servers or partial/truncated context snapshots fall back to the
    established detailed manifest. This keeps compatibility while preventing the
    WebUI's 30-second dashboard poll from forcing a detailed per-device refresh on
    servers that expose the bulk resource.
    """

    try:
        context = await mcp.get_live_context()
        if live_context_is_complete(context):
            return live_context_devices(context), "bulk-live-context"
        logger.warning("Dashboard live context was partial; using detailed manifest")
    except Exception as exc:
        logger.warning("Dashboard live context unavailable; using detailed manifest: %s", exc)
    return list(await mcp.get_cached_devices()), "detailed-manifest"


@app.get("/api/dashboard")
async def dashboard() -> dict[str, Any]:
    try:
        devices, source = await _dashboard_devices()
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

    # Rich hub-info attributes are not part of the compact context resource.
    # Reuse a detailed manifest only if one is already cached; never trigger an
    # expensive detailed refresh merely to decorate the dashboard payload.
    detailed = mcp.peek_cached_devices()
    hub_info_devices = detailed if detailed else devices
    return {
        "success": True,
        "source": source,
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
        "hub_info": _hub_info(hub_info_devices),
    }


@app.get("/api/health-audit")
async def health_audit_status() -> dict[str, Any]:
    return {
        "success": True,
        "latest": health_audit.latest(),
        "schedule": health_scheduler.status(),
    }


@app.post("/api/health-audit/run")
async def run_health_audit() -> dict[str, Any]:
    try:
        latest = await request_coordinator.run(
            "system-health-audit",
            health_audit.run(reason="manual"),
        )
    except Exception as exc:
        logger.exception("Manual system health audit failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "success": True,
        "latest": latest,
        "schedule": health_scheduler.status(),
    }


@app.get("/api/one-time-rule-cleanup")
async def one_time_rule_cleanup_status() -> dict[str, Any]:
    return {
        "success": True,
        "schedule": one_time_rule_cleanup_scheduler.status(),
    }


@app.post("/api/one-time-rule-cleanup/run")
async def run_one_time_rule_cleanup() -> dict[str, Any]:
    try:
        result = await request_coordinator.run(
            "one-time-rule-cleanup",
            one_time_rule_cleanup_scheduler.run_now(),
        )
    except Exception as exc:
        logger.exception("Manual one-time rule cleanup failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    payload = result.as_dict()
    return {
        "success": not bool(result.list_error),
        "result": payload,
        "schedule": one_time_rule_cleanup_scheduler.status(),
    }


@app.post("/api/tts")
async def speak_tts(payload: TTSRequest, request: Request) -> dict[str, Any]:
    try:
        delivery = await home_assistant_tts.speak(
            payload.text,
            device_hint=str(request.headers.get("user-agent") or ""),
        )
    except HomeAssistantTTSConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("Home Assistant native TTS delivery failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Home Assistant TTS delivery failed: {str(exc)[:240]}",
        ) from exc
    return {
        "success": True,
        **delivery,
    }


@app.post("/api/tts/stop")
async def stop_tts() -> dict[str, Any]:
    try:
        delivery = await home_assistant_tts.stop()
    except HomeAssistantTTSConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("Home Assistant native TTS stop failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Home Assistant TTS stop failed: {str(exc)[:240]}",
        ) from exc
    return {
        "success": True,
        **delivery,
    }


@app.post("/api/pushover/report")
async def send_pushover_report() -> dict[str, Any]:
    if not pushover_notifier.enabled:
        raise HTTPException(status_code=409, detail="Pushover notifications are disabled")
    if not pushover_notifier.configured:
        raise HTTPException(
            status_code=409,
            detail="Pushover application token or user/group key is missing",
        )
    try:
        latest = health_audit.latest()
        if not isinstance(latest, dict):
            raise HTTPException(
                status_code=409,
                detail="No System Check report is available. Run system check first.",
            )
        delivery = await pushover_notifier.send(latest)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Manual Pushover report delivery failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Pushover delivery failed: {str(exc)[:240]}",
        ) from exc
    messages_sent = max(1, int(delivery.get("messages_sent") or 1))
    delivery_message = (
        "Latest System Check report sent to Pushover."
        if messages_sent == 1
        else f"Latest System Check report sent to Pushover in {messages_sent} messages."
    )
    return {
        "success": True,
        "message": delivery_message,
        "request": str(delivery.get("request") or ""),
        "messages_sent": messages_sent,
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


class V2TestRequest(BaseModel):
    question: str = Field(min_length=5, max_length=12000)
    device_ids: list[str] = Field(default_factory=list, max_length=4)
    device_name: str | None = Field(default=None, max_length=160)
    explicit_opt_in: bool = False
    existing_v1_answer: str | None = Field(default=None, max_length=30000)
    reference_answer: str | None = Field(default=None, max_length=30000)


@app.get("/v2-test", response_class=HTMLResponse)
async def v2_test_panel() -> HTMLResponse:
    enabled = _bool(OPTIONS.get("investigation_v2_testing_enabled"), False)
    secret = str(OPTIONS.get("investigation_v2_test_token") or "")
    if not enabled or len(secret) < 16:
        raise HTTPException(status_code=404, detail="V2 test mode is disabled")
    return HTMLResponse(render_v2_test_page(), headers={"Cache-Control":"no-store"})


def _v2_browser_enabled() -> tuple[bool, str]:
    enabled = _bool(OPTIONS.get("investigation_v2_testing_enabled"), False)
    secret = str(OPTIONS.get("investigation_v2_test_token") or "")
    return enabled and len(secret) >= 16, secret


@app.get("/api/v2/auth/status")
async def v2_test_auth_status(connection: Request) -> JSONResponse:
    """No-store status only. Never expose the configured secret or cookie."""
    enabled, configured = _v2_browser_enabled()
    saved = enabled and verify_browser_access(
        connection.cookies.get(COOKIE_NAME), configured,
    )
    return JSONResponse(
        {"saved_access": saved},
        headers={"Cache-Control": "no-store"},
    )


@app.post("/api/v2/auth/remember")
async def v2_test_auth_remember(connection: Request) -> JSONResponse:
    """Explicit operator opt-in to a 30-day, HttpOnly, revocable cookie."""
    enabled, configured = _v2_browser_enabled()
    provided = str(connection.headers.get("x-homebrain-v2-test-token") or "")
    try:
        require_test_access(
            enabled=enabled, configured_token=configured,
            supplied_token=provided, explicit_opt_in=True,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="V2 test authorization failed") from None
    value = mint_browser_access(configured)
    response = JSONResponse({"saved_access": True},
                            headers={"Cache-Control": "no-store"})
    response.set_cookie(
        key=COOKIE_NAME, value=value, max_age=COOKIE_AGE_SECONDS,
        expires=COOKIE_AGE_SECONDS, path="/", httponly=True,
        secure=connection.url.scheme == "https", samesite="strict",
    )
    return response


@app.post("/api/v2/auth/forget")
async def v2_test_auth_forget(connection: Request) -> JSONResponse:
    # A custom application header prevents a cross-site HTML form from
    # silently signing the operator out. No live hub/device actions.
    if connection.headers.get("x-homebrain-v2-request") != "read-only":
        raise HTTPException(status_code=403, detail="V2 browser request rejected")
    response = JSONResponse({"saved_access": False},
                            headers={"Cache-Control": "no-store"})
    response.delete_cookie(key=COOKIE_NAME, path="/", samesite="strict",
                           secure=connection.url.scheme == "https", httponly=True)
    return response


@app.post("/api/v2/test")
async def v2_test(payload: V2TestRequest, connection: Request) -> dict[str, Any]:
    """Manual experiment only: no production agent route or Hubitat mutation."""
    enabled = _bool(OPTIONS.get("investigation_v2_testing_enabled"), False)
    configured = str(OPTIONS.get("investigation_v2_test_token") or "")
    provided = str(connection.headers.get("x-homebrain-v2-test-token") or "")
    if not provided:
        # Cookies are accepted only on explicitly labelled same-origin
        # read-only fetch requests, not cross-site form submissions.
        browser_intent = connection.headers.get("x-homebrain-v2-request")
        if browser_intent == "read-only" and verify_browser_access(
            connection.cookies.get(COOKIE_NAME), configured,
        ):
            provided = configured  # Host-side equivalence; never serialized.
    try:
        require_test_access(enabled=enabled, configured_token=configured,
                            supplied_token=provided,
                            explicit_opt_in=payload.explicit_opt_in)
    except PermissionError as exc:
        if str(exc) == "v2_test_disabled":
            raise HTTPException(status_code=404, detail="V2 test mode is disabled") from None
        raise HTTPException(status_code=403, detail="V2 test authorization failed") from None

    # The production classifier already distinguishes explicit commands
    # from causal questions about commands. Use it only as a NEGATIVE V2
    # boundary: it cannot grant write authority or select a Hubitat tool.
    # Reject before inventory/AI/MCP work, even with an Advanced ID override.
    if incompatible_v2_control_request(payload.question):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "v2_control_not_supported",
                "message": (
                    "This is a device-control request, not a read-only "
                    "investigation. No Hubitat command was sent. "
                    "Use HomeBrain's main Ask/Chat interface to request "
                    "the action, subject to its normal write permissions "
                    "and confirmation checks."
                ),
            },
        )

    async def experiment() -> dict[str, Any]:
        started = time.perf_counter()
        semantic = None
        semantic_failure = None
        direct_verified_target = None
        audit_devices = None
        if not payload.device_ids and not payload.device_name:
            # Source discovery, intent planning, and optional measurement
            # classification are separate, observable stages. None of them
            # grants tool or device-control authority to the model.
            inventory_started=time.perf_counter()
            identity_inventory_ms=0
            full_inventory_ms=0
            try:
                # A single verified named-device read needs only IDs/labels.
                # Keep the live total, pagination, uniqueness and generation
                # checks; never promote cached/model names into authority.
                identity_started=time.perf_counter()
                # A prior complete projected inventory can be reused for a
                # short READ-ONLY V2 test interval. Writes invalidate it by
                # generation; stale, incomplete and ambiguous snapshots fall
                # back to a fresh, total-verified page audit.
                recent = mcp.recent_verified_audit_identities()
                if recent is not None:
                    audit_devices, inventory_provenance = recent
                else:
                    audit_devices, inventory_provenance = await mcp.get_audit_devices(
                    identity_only=True)
                identity_inventory_ms=round(
                    (time.perf_counter()-identity_started)*1000)
                try:
                    candidates, _, _ = resolve_verified_device_subjects(
                        payload.question, audit_devices)
                except ValueError:
                    candidates = ()
                # Broad and ambiguous questions still require a complete
                # state/capability vocabulary. The identity-only projection
                # must never feed a whole-house state result.
                if (not (len(candidates)==1
                         and inventory_provenance.get("complete") is True)
                        and inventory_provenance.get("projection")=="identity_only"):
                    full_started=time.perf_counter()
                    audit_devices, inventory_provenance = await mcp.get_audit_devices()
                    full_inventory_ms=round(
                        (time.perf_counter()-full_started)*1000)
                    try:
                        candidates, _, _ = resolve_verified_device_subjects(
                            payload.question, audit_devices)
                    except ValueError:
                        candidates = ()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("V2 fresh inventory unavailable")
                raise HTTPException(
                    status_code=503,
                    detail="Hubitat read-only inventory was unavailable; no commands sent",
                ) from None
            inventory_ms=round((time.perf_counter()-inventory_started)*1000)
            # Diagnostic provenance stays tied to the actual Hubitat source.
            # Times include client transport/queue waits; never label them
            # measured hub CPU time, or infer that a partial page is complete.
            _pages=inventory_provenance.get("page_timings_ms")
            inventory_page_diagnostics={
                "source": inventory_provenance.get("source"),
                "mode": inventory_provenance.get("mode"),
                "pages": inventory_provenance.get("pages"),
                "first_page_ms": inventory_provenance.get("first_page_ms"),
                "slowest_page_ms": inventory_provenance.get("slowest_page_ms"),
                "parallel_page_max_concurrent": inventory_provenance.get(
                    "parallel_page_max_concurrent"),
                "page_timings_ms": [
                    {"offset": row.get("offset"), "elapsed_ms": row.get("elapsed_ms"),
                     "success": row.get("success") is True}
                    for row in _pages[:10] if isinstance(row, dict)
                ] if isinstance(_pages, list) else [],
            }
            if (len(candidates) == 1
                    and inventory_provenance.get("complete") is True):
                direct_verified_target = candidates[0]
                planning_ms = 0
            else:
                planning_started=time.perf_counter()
                try:
                    semantic = await semantic_plan(
                        payload.question, audit_devices, agent.transport.chat,
                        timeout_seconds=25,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    cause=("timeout" if isinstance(exc,TimeoutError)
                           else "invalid_plan" if isinstance(exc,(ValueError,TypeError,KeyError))
                           else "provider_failure")
                    logger.warning("V2 semantic plan unavailable: %s (%s)",
                                   cause,type(exc).__name__)
                    # If the real user named EXACTLY one inventory-verified
                    # device, AI intent classification is not an authorisation
                    # dependency for bounded read-only evidence collection.
                    # No guessed ID, keyword router, or model-selected target.
                    try:
                        fallback_ids, _, _ = resolve_verified_device_subjects(
                            payload.question, audit_devices)
                    except ValueError:
                        fallback_ids = ()
                    if len(fallback_ids) == 1:
                        semantic_failure = cause
                        logger.info("V2 single-device read-only fallback: %s", cause)
                    else:
                        message=(
                            "HomeBrain retrieved Hubitat inventory, but could not "
                            "safely interpret the question. No device commands were "
                            "sent. Check the planning diagnostics in the report."
                        )
                        return {
                            "answer_mode":"semantic_unavailable",
                            "answer":{"text":message,"displayed_record_ids":[],
                                      "omitted_material_record_ids":[],
                                      "validation_issues":["semantic_plan_"+cause],
                                      "root_cause_verified":False,"human_review_required":True},
                            "report":{"text":message,"technical_answer_retained":False},
                            "semantic_diagnostics":{
                                "phase":"intent_planning","outcome":cause,
                                "inventory_ms":inventory_ms,
                                "planning_ms":round((time.perf_counter()-planning_started)*1000),
                                "inventory_devices":len(audit_devices),
                                "inventory_complete":inventory_provenance.get("complete") is True,
                            },
                            "resolved_devices":[],"resolution_method":"semantic_objective",
                            "elapsed_ms":round((time.perf_counter()-started)*1000),
                            "test_mode":"explicit_read_only",
                        }
                planning_ms=round((time.perf_counter()-planning_started)*1000)
            if semantic is not None and semantic.mode == "inventory":
                if semantic.scope == "named":
                    try:
                        semantic = ground_named_inventory_plan(
                            semantic, payload.question, audit_devices)
                    except ValueError as exc:
                        raise HTTPException(status_code=422, detail=str(exc)) from None
                enrichment_started=time.perf_counter()
                semantic, role_diagnostic=await enrich_measurement_roles(
                    semantic, audit_devices, agent.transport.chat,
                    timeout_seconds=12,
                )
                try:
                    result = execute_inventory_plan(
                        semantic, audit_devices, inventory_provenance,
                        operator_roles=load_operator_meter_roles(
                            OPTIONS.get("v2_measurement_roles_json", "{}"),
                            audit_devices,
                        ),
                    )
                except ValueError as exc:
                    raise HTTPException(status_code=422,detail=str(exc)) from None
                result["elapsed_ms"]=round((time.perf_counter()-started)*1000)
                if semantic.scope == "named" and semantic.device_names:
                    ids, resolved, _ = resolve_verified_device_subjects(
                        payload.question, audit_devices)
                    result["resolved_devices"] = resolved
                    result["resolution_method"] = "verified_named_multi"
                result["semantic_diagnostics"]={
                    "phase":"completed","outcome":"success",
                    "inventory_ms":inventory_ms,"planning_ms":planning_ms,
                    "identity_inventory_ms":identity_inventory_ms,
                    "full_inventory_ms":full_inventory_ms,
                    "inventory_projection":inventory_provenance.get("projection"),
                    "role_enrichment_ms":round((time.perf_counter()-enrichment_started)*1000),
                    "meter_roles":role_diagnostic,
                    "inventory_devices":len(audit_devices),
                    "inventory_complete":inventory_provenance.get("complete") is True,
                }
                if role_diagnostic.get("outcome")=="unavailable":
                    result["answer"]["validation_issues"].append(
                        "optional_measurement_role_enrichment_unavailable"
                    )
                return result
            if semantic is not None and semantic.mode in ("unsupported","historical"):
                # Unsupported whole-house history must not be misrepresented
                # as a present-state inventory query or fabricated timeline.
                subject=("A cross-device historical comparison" if
                         semantic.mode=="historical" else "This question")
                message=(subject+" is not yet supported by the safe V2 "
                         "inventory executor. Current inventory answers and "
                         "single-device investigation are available; no "
                         "device state was changed.")
                return {
                    "answer_mode":"semantic_unavailable",
                    "answer":{"text":message,"displayed_record_ids":[],
                              "omitted_material_record_ids":[],
                              "validation_issues":["unsupported_evidence_objective"],
                              "root_cause_verified":False,"human_review_required":True},
                    "report":{"text":message,"technical_answer_retained":False},
                    "semantic_plan":semantic.to_dict(),
                    "resolved_devices":[],"resolution_method":"semantic_objective",
                    "elapsed_ms":round((time.perf_counter()-started)*1000),
                    "test_mode":"explicit_read_only",
                }
        try:
            # Named historical cases retain the existing strict read plan.
            # Device identities may come from the *model's phrase*, but only
            # live Hubitat names/IDs can satisfy the host verification gate.
            devices = (audit_devices if audit_devices is not None
                       else await mcp.get_cached_devices(refresh=True))
            if payload.device_ids or payload.device_name:
                # Explicit operator overrides keep their strict verification.
                ids, resolved, resolve_method = resolve_verified_device_subjects(
                    payload.question, devices, device_name=payload.device_name,
                    device_ids=payload.device_ids)
            else:
                # An AI name proposal must not override a clear name in the
                # question. Live Hubitat identity remains authoritative.
                ids, resolved, resolve_method = resolve_planned_device_subjects(
                    payload.question, devices,
                    model_device_name=(semantic.device_name if semantic is not None
                                       and semantic.scope=="named" else None))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        except Exception:
            raise HTTPException(status_code=503, detail="Hubitat identity verification unavailable") from None
        # Hub time is obtained from existing authoritative resolver. If
        # unavailable, do not silently invent a calendar: use UTC and show
        # the fallback basis in the explicit window metadata.
        zone_name = "UTC"
        # Use the same calendar parser as Investigation V2: a single
        # explicit date is an incident window too, not a UTC-only request.
        # Never guess the hub zone from the server or browser locale.
        if explicit_incident_window(payload.question, zone_name="UTC") is not None:
            try:
                _now_local, resolved_zone, _zone_basis = await _health_timezone.now_in_hub_timezone(
                    lambda: datetime.now(timezone.utc))
                if resolved_zone:
                    zone_name = resolved_zone
            except Exception:
                pass
        incident_window = explicit_incident_window(
            payload.question, zone_name=zone_name,
            now=datetime.now(timezone.utc),
        )
        factual_objective = (verified_factual_objective(
            payload.question, [item["label"] for item in resolved])
            if len(resolved) == 1 and semantic_failure is None else None)
        try:
            evaluated = await evaluate_v2_with_model(
                explicitly_authorised=True,
                question=payload.question,
                chat=agent.transport.chat,
                mcp=mcp, executor=agent.executor,
                verified_entity_ids=ids,
                enable_atomic_claim_validation=True,
                enable_evidence_narrative=True,
                bootstrap_device_context=True,
                semantic_unavailable_reason=semantic_failure,
                max_rounds=2, max_total_reads=8,
                # Factual status/history queries never invoke this planner.
                # Causal analysis needs time to select useful evidence rather
                # than hitting the observed 15-second provider ceiling. Keep
                # a bounded timeout; any later causal claim still needs proof.
                planning_timeout_seconds=(35.0 if factual_objective is None else 15.0),
                incident_window=incident_window,
                verified_device_label=resolved[0]["label"] if len(resolved)==1 else None,
                force_duration_mode=semantic is not None and semantic.mode=="duration",
                factual_objective=factual_objective,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Opt-in V2 evaluation unavailable")
            raise HTTPException(status_code=503, detail="V2 evaluation failed; no Hubitat writes attempted") from None
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        result = evaluated.to_dict()
        result["elapsed_ms"] = elapsed_ms
        result["test_mode"] = "explicit_read_only"
        result["resolved_devices"] = resolved
        result["resolution_method"] = resolve_method
        if direct_verified_target is not None:
            result["answer_mode"] = ("verified_device_" + factual_objective
                                     if factual_objective else "verified_device_investigation")
            result["semantic_diagnostics"] = {
                "phase": "evidence_first_verified_device",
                "outcome": "direct_verified_target",
                "inventory_ms": inventory_ms,
                "identity_inventory_ms": identity_inventory_ms,
                "full_inventory_ms": full_inventory_ms,
                "inventory_projection": inventory_provenance.get("projection"),
                "inventory_page_diagnostics": inventory_page_diagnostics,
                "planning_ms": 0,
                "inventory_devices": len(audit_devices),
                "inventory_complete": inventory_provenance.get("complete") is True,
                "target_verified": True,
                "target_id": direct_verified_target,
                "model_intent_planning_skipped": True,
                "model_investigation_attempted": factual_objective is None,
                "factual_objective": factual_objective,
            }
        if semantic_failure is not None:
            result["answer_mode"] = "semantic_fallback_investigation"
            result["semantic_diagnostics"] = {
                "phase": "host_only_evidence_recovery",
                "outcome": "partial_evidence_recovered",
                "reason": semantic_failure,
                "inventory_ms": inventory_ms,
                "planning_ms": planning_ms,
                "inventory_devices": len(audit_devices),
                "inventory_complete": inventory_provenance.get("complete") is True,
                "target_verified": True,
                "model_investigation_attempted": False,
            }
        if semantic is not None:
            result["semantic_plan"] = semantic.to_dict()
            result["answer_mode"] = ("semantic_duration" if semantic.mode=="duration"
                                    else "semantic_investigation")
        if factual_objective is not None and direct_verified_target is None:
            result["answer_mode"] = "verified_device_" + factual_objective
        result["scorecard"] = replay_scorecard(
            evaluated.investigation.case, evaluated.answer,
            existing_v1_answer=payload.existing_v1_answer,
            reference_answer=payload.reference_answer,
            reads_executed=evaluated.investigation.executed_reads,
            elapsed_ms=elapsed_ms,
        )
        return result

    # Separate coordinator key: never cancel or reuse a production chat.
    return await request_coordinator.run(
        "investigation-v2-test-exclusive", experiment(),
        connection=connection, request_id=uuid.uuid4().hex,
        deadline_seconds=240,
    )


@app.post("/api/chat")
async def chat(request: ChatRequest, connection: Request) -> dict[str, Any]:
    return {"response": await _answer(request, connection)}


@app.post("/api/ask")
async def ask(request: ChatRequest, connection: Request) -> dict[str, Any]:
    started = time.perf_counter()
    outcome = await _answer_result(request, connection)
    result = build_agent_response(
        outcome,
        model=agent.model_name,
        elapsed_ms=round((time.perf_counter() - started) * 1000),
        version=VERSION,
    )
    result["model_tier_requested"] = request.model_tier
    return result


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8788, log_level="info", proxy_headers=True)
