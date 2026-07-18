from __future__ import annotations

import asyncio

import uvicorn
from pydantic import Field

import app as application
import device_intelligence_webui as device_intelligence_webui_module
import ollama_engagement as ollama_engagement_module
from automation_recommendation import install_automation_recommendation
from automation_recommendation_webui import install_automation_recommendation_webui
from automation_rule_workflow_washing import (
    install_washing_rule_machine_workflow as install_automation_rule_workflow,
)
from cancellable_requests import install_cancellable_ask
from control_confirmation import install_control_confirmation
from control_language import install_control_language
from conversation_context_safe import install_safe_conversation_context
from dashboard_api import install_dashboard_api
from device_index_broker import IndexedMCPStateBroker
from device_intelligence_api import install_device_intelligence_api
from device_intelligence_duplicate_safe import DuplicateAwareCapabilityCatalogueDeviceIndex
from device_intelligence_webui import install_device_intelligence_webui
from fast_fallback_engagement import FastFallbackRouter
from fastpath_ai_handoff import install_fastpath_ai_handoff
from home_snapshot_hybrid import install_hybrid_home_snapshot
from mcp_tool_catalogue import install_mcp_tool_catalogue
from motion_light_insight import install_motion_light_insight
from ollama_agent_adaptive import AdaptiveFinalAnswerAgent
from ollama_cloud_help import hybrid_ollama_help
from ollama_diagnostics_hybrid import install_hybrid_ollama_diagnostics
from ollama_engagement import install_ollama_engagement
from ollama_hybrid_profile import resolve_hybrid_profile
from request_tracing import install_request_tracing
from temperature_insight_hybrid import HybridTemperatureInsightService


PREVIOUS_RELEASE_VERSION = "0.4.20-alpha"
RELEASE_VERSION = "0.4.21-alpha"


class ContextAskRequest(application.AskRequest):
    """Ask payload with a stable per-browser session used for short-lived context."""

    session_id: str | None = Field(default=None, max_length=160)


application.AskRequest = ContextAskRequest


def _replace_mcp_client() -> None:
    options = application.OPTIONS
    application.mcp = IndexedMCPStateBroker(
        application.mcp,
        device_ttl_seconds=float(options.get("mcp_device_cache_seconds") or 12),
        catalog_ttl_seconds=float(options.get("mcp_catalog_cache_seconds") or 60),
        hub_ttl_seconds=float(options.get("mcp_hub_cache_seconds") or 20),
    )


def _create_device_index() -> DuplicateAwareCapabilityCatalogueDeviceIndex:
    options = application.OPTIONS
    index = DuplicateAwareCapabilityCatalogueDeviceIndex(
        application.mcp,
        ttl_seconds=float(options.get("device_index_ttl_seconds") or 15),
        capability_ttl_seconds=float(options.get("device_index_capability_ttl_seconds") or 60),
        metadata_ttl_seconds=float(options.get("device_index_metadata_ttl_seconds") or 120),
    )
    application.device_index = index
    return index


def _replace_fallback_router(index: DuplicateAwareCapabilityCatalogueDeviceIndex) -> None:
    application.fallback = FastFallbackRouter(
        application.mcp,
        device_index=index,
        attention_stale_hours=float(application.OPTIONS.get("attention_stale_hours") or 48),
        cpu_probe_enabled=application.option_bool("hub_cpu_probe_enabled", True),
        cpu_probe_timeout_seconds=float(application.OPTIONS.get("hub_cpu_probe_timeout_seconds") or 2.5),
        control_verification_timeout_seconds=float(application.OPTIONS.get("control_verification_timeout_seconds") or 7),
    )


def _replace_ollama_agent() -> None:
    previous = application.ollama
    options = application.OPTIONS
    profile = resolve_hybrid_profile(options)
    application.ollama_hybrid_profile = profile

    application.ollama = AdaptiveFinalAnswerAgent(
        client=application.mcp,
        base_url=str(options.get("ollama_base_url") or ""),
        model=str(profile["effective_response_model"]),
        planner_model=str(profile["planner_model"]),
        routine_model=str(profile["effective_routine_model"]),
        cloud_enabled=bool(profile["cloud_enabled"]),
        cloud_model=str(profile["cloud_model"]),
        local_fallback_model=str(profile["local_fallback_model"]),
        cloud_fallback_local=application.option_bool(
            "ollama_cloud_fallback_local",
            True,
        ),
        cloud_timeout_seconds=float(
            options.get("ollama_cloud_timeout_seconds") or 12
        ),
        health_timeout_seconds=float(options.get("ollama_health_timeout_seconds") or 3),
        planner_timeout_seconds=max(10.0, float(options.get("ollama_planner_timeout_seconds") or 20)),
        response_timeout_seconds=float(options.get("ollama_response_timeout_seconds") or 30),
        routine_response_timeout_seconds=float(options.get("ollama_routine_response_timeout_seconds") or 20),
        num_ctx=int(options.get("ollama_num_ctx") or 2048),
        num_predict=int(options.get("ollama_num_predict") or 160),
        keep_alive=str(options.get("ollama_keep_alive") or "30m"),
        planner_tool_limit=int(options.get("ollama_planner_tool_limit") or 4),
        tool_result_limit_chars=int(options.get("ollama_tool_result_limit_chars") or 4000),
        max_tool_rounds=int(options.get("ollama_max_tool_rounds") or 2),
        require_sensitive_confirmation=application.option_bool("require_sensitive_confirmation", True),
        fallback_provider=application.fallback.answer,
        evidence_item_limit=int(options.get("ollama_evidence_item_limit") or 8),
    )

    try:
        asyncio.run(previous.close())
    except Exception:
        pass


_replace_mcp_client()
device_index = _create_device_index()
_replace_fallback_router(device_index)
_replace_ollama_agent()
install_hybrid_ollama_diagnostics(application)
install_fastpath_ai_handoff(application)
home_snapshot = install_hybrid_home_snapshot(
    application,
    device_index,
    ai_enabled=application.option_bool("home_snapshot_ai_enabled", True),
    ai_timeout_seconds=float(application.OPTIONS.get("home_snapshot_ai_timeout_seconds") or 20),
    max_items_per_group=int(application.OPTIONS.get("home_snapshot_max_items_per_group") or 8),
)
# The engagement installer constructs bounded services and help from its module
# globals. Replace those before installation so all responses use the hybrid
# Cloud/local implementations and accurate ownership labels.
ollama_engagement_module.TemperatureInsightService = HybridTemperatureInsightService
ollama_engagement_module.ollama_help = hybrid_ollama_help
ollama_engagement = install_ollama_engagement(application, home_snapshot)
motion_light_insight = install_motion_light_insight(
    application,
    device_index,
    ai_timeout_seconds=float(
        application.OPTIONS.get("ollama_quick_insight_timeout_seconds") or 20
    ),
)
automation_recommendation = install_automation_recommendation(
    application,
    device_index,
    ai_timeout_seconds=float(
        application.OPTIONS.get("ollama_quick_insight_timeout_seconds") or 20
    ),
)
conversation_context = install_safe_conversation_context(
    application,
    device_index,
    ttl_seconds=float(application.OPTIONS.get("conversation_context_ttl_seconds") or 600),
    max_sessions=int(application.OPTIONS.get("conversation_context_max_sessions") or 128),
    max_group_control=int(application.OPTIONS.get("conversation_context_max_group_control") or 8),
)
control_confirmations = install_control_confirmation(
    application,
    ttl_seconds=float(application.OPTIONS.get("control_confirmation_ttl_seconds") or 120),
    max_sessions=int(application.OPTIONS.get("conversation_context_max_sessions") or 128),
)
install_control_language(application)
automation_rule_workflow = install_automation_rule_workflow(
    application,
    device_index,
    ttl_seconds=float(application.OPTIONS.get("rule_workflow_ttl_seconds") or 600),
    max_sessions=int(application.OPTIONS.get("conversation_context_max_sessions") or 128),
    write_enabled=application.option_bool("rule_write_enabled", True),
    require_paused_create=application.option_bool("rule_create_paused_required", True),
)
request_traces = install_request_tracing(
    application,
    application.mcp,
    limit=int(application.OPTIONS.get("request_trace_limit") or 20),
)
dashboard_snapshot = install_dashboard_api(
    application,
    ttl_seconds=float(application.OPTIONS.get("dashboard_refresh_seconds") or 30),
    device_index=device_index,
)


async def _invalidate_dashboard(category: str) -> None:
    if category in {"devices", "all"}:
        await dashboard_snapshot.invalidate()


application.mcp.register_invalidator(_invalidate_dashboard)
install_device_intelligence_api(application, device_index)
install_mcp_tool_catalogue(application, application.mcp)
request_registry = install_cancellable_ask(application)
application.VERSION = RELEASE_VERSION
application.app.version = RELEASE_VERSION
install_automation_recommendation_webui(device_intelligence_webui_module)
install_device_intelligence_webui(application)
app = application.app


@app.on_event("startup")
async def warm_device_intelligence_index() -> None:
    try:
        await asyncio.gather(device_index.summary_result(), device_index.metadata_result())
    except Exception:
        pass


@app.on_event("shutdown")
async def cancel_active_requests() -> None:
    await request_registry.cancel_all()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8788, log_level="info", proxy_headers=True)
