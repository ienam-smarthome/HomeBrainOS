from __future__ import annotations

import asyncio

import uvicorn
from pydantic import Field

import app as application
import device_intelligence_webui as device_intelligence_webui_module
import ollama_engagement as ollama_engagement_module
from ai_evidence_domains import install_ai_evidence_domains
from ai_evidence_planner import install_ai_evidence_planner
from automation_recommendation import (
    install_automation_recommendation,
    install_automation_recommendation_terminal_route,
)
from automation_recommendation_webui import install_automation_recommendation_webui
from automation_rule_direct_contact import (
    install_direct_contact_rule_workflow as install_washing_rule_machine_workflow,
)
from cancellable_requests import install_cancellable_ask
from control_agent_combined_level import install_combined_level_intent
from control_agent_gate import install_control_agent_gate
from control_agent_postfix_control import install_postfix_control_intent
from control_agent_rescue import install_control_agent
from control_confirmation import install_control_confirmation
from control_language import install_control_language
from conversation_context_safe import install_safe_conversation_context
from dashboard_api import install_dashboard_api
from dashboard_health_tile import install_dashboard_health_tile
from device_health_fast_route import install_device_health_fast_route
from device_index_broker import IndexedMCPStateBroker
from device_intelligence_api import install_device_intelligence_api
from device_intelligence_duplicate_safe import DuplicateAwareCapabilityCatalogueDeviceIndex
from device_intelligence_webui import install_device_intelligence_webui
from device_refresh_webui import install_device_refresh_webui
from fast_fallback_light_usage import FastFallbackRouter
from fastpath_ai_handoff import install_fastpath_ai_handoff
from home_snapshot_hybrid import install_hybrid_home_snapshot
from hub_backup_workflow import install_explicit_hub_backup_workflow
from hybrid_assistant_mode import (
    install_hybrid_assistant_query_policy,
    install_hybrid_verified_read_routes,
)
from mcp_agent_orchestrator import install_unified_mcp_agent_orchestrator
from hub_restart_workflow import install_hub_restart_workflow
from mcp_tool_catalogue import install_mcp_tool_catalogue
from motion_light_insight import install_motion_light_insight
from named_rule_control import install_named_rule_controller
from ollama_agent_unified import UnifiedAdaptiveMCPAgent
from ollama_cloud_help import hybrid_ollama_help
from ollama_diagnostics_hybrid import install_hybrid_ollama_diagnostics
from ollama_engagement import install_ollama_engagement, install_ollama_help_terminal_route
from ollama_hybrid_profile import resolve_hybrid_profile
from request_tracing import install_request_tracing
from semantic_metric_comparison_live import SemanticMetricComparisonExecutor
from semantic_read_pipeline import install_semantic_read_pipeline
from temperature_insight_hybrid import HybridTemperatureInsightService
from webui_clipboard_safe import install_clipboard_safe_webui
from webui_http_safe import install_http_safe_webui


PREVIOUS_RELEASE_VERSION = "0.10.9"
RELEASE_VERSION = "0.10.14"
install_automation_rule_workflow = install_washing_rule_machine_workflow


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

    application.ollama = UnifiedAdaptiveMCPAgent(
        client=application.mcp,
        base_url=str(options.get("ollama_base_url") or ""),
        model=str(profile["effective_response_model"]),
        planner_model=str(profile["planner_model"]),
        routine_model=str(profile["effective_routine_model"]),
        cloud_enabled=bool(profile["cloud_enabled"]),
        cloud_model=str(profile["cloud_model"]),
        local_fallback_model=str(profile["local_fallback_model"]),
        cloud_fallback_local=application.option_bool("ollama_cloud_fallback_local", True),
        cloud_timeout_seconds=float(options.get("ollama_cloud_timeout_seconds") or 12),
        direct_cloud_enabled=application.option_bool("ollama_direct_cloud_enabled", True),
        direct_cloud_base_url=str(options.get("ollama_direct_cloud_base_url") or "https://ollama.com"),
        direct_cloud_api_key=str(options.get("ollama_direct_cloud_api_key") or ""),
        direct_cloud_model=str(options.get("ollama_direct_cloud_model") or ""),
        direct_cloud_fallback_local_proxy=application.option_bool(
            "ollama_direct_cloud_fallback_local_proxy", True
        ),
        health_timeout_seconds=float(options.get("ollama_health_timeout_seconds") or 3),
        planner_timeout_seconds=max(10.0, float(options.get("ollama_planner_timeout_seconds") or 25)),
        response_timeout_seconds=float(options.get("ollama_response_timeout_seconds") or 35),
        routine_response_timeout_seconds=float(options.get("ollama_routine_response_timeout_seconds") or 25),
        num_ctx=int(options.get("ollama_num_ctx") or 8192),
        num_predict=int(options.get("ollama_num_predict") or 240),
        keep_alive=str(options.get("ollama_keep_alive") or "30m"),
        planner_tool_limit=int(options.get("ollama_planner_tool_limit") or 40),
        unified_tool_limit=int(options.get("unified_mcp_tool_limit") or 48),
        tool_result_limit_chars=int(options.get("ollama_tool_result_limit_chars") or 8000),
        max_tool_rounds=int(options.get("ollama_max_tool_rounds") or 6),
        require_sensitive_confirmation=application.option_bool("require_sensitive_confirmation", True),
        fallback_provider=application.fallback.answer,
        evidence_item_limit=int(options.get("ollama_evidence_item_limit") or 8),
    )

    try:
        asyncio.run(previous.close())
    except Exception:
        pass


install_dashboard_health_tile()
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
ollama_engagement_module.TemperatureInsightService = HybridTemperatureInsightService
ollama_engagement_module.ollama_help = hybrid_ollama_help
ollama_engagement = install_ollama_engagement(application, home_snapshot)
motion_light_insight = install_motion_light_insight(
    application,
    device_index,
    ai_timeout_seconds=float(application.OPTIONS.get("ollama_quick_insight_timeout_seconds") or 20),
)
automation_recommendation = install_automation_recommendation(
    application,
    device_index,
    ai_timeout_seconds=float(application.OPTIONS.get("ollama_quick_insight_timeout_seconds") or 20),
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
install_combined_level_intent()
install_postfix_control_intent()
legacy_control_ask = application.ask
control_agent = install_control_agent(
    application,
    device_index,
    application.fallback,
    intent_timeout_seconds=float(application.OPTIONS.get("control_agent_intent_timeout_seconds") or 5),
    context_ttl_seconds=float(application.OPTIONS.get("conversation_context_ttl_seconds") or 600),
    confirmation_ttl_seconds=float(application.OPTIONS.get("control_confirmation_ttl_seconds") or 120),
    max_sessions=int(application.OPTIONS.get("conversation_context_max_sessions") or 128),
    auto_execute_confidence=float(application.OPTIONS.get("control_agent_auto_execute_confidence_percent") or 88) / 100.0,
    block_below_confidence=float(application.OPTIONS.get("control_agent_block_below_confidence_percent") or 50) / 100.0,
    group_confirmation_size=int(application.OPTIONS.get("control_agent_group_confirmation_size") or 6),
    level_verification_timeout_seconds=float(application.OPTIONS.get("control_level_verification_timeout_seconds") or 3),
)
install_control_agent_gate(application, control_agent, legacy_control_ask)
automation_rule_workflow = install_automation_rule_workflow(
    application,
    device_index,
    ttl_seconds=float(application.OPTIONS.get("rule_workflow_ttl_seconds") or 600),
    max_sessions=int(application.OPTIONS.get("conversation_context_max_sessions") or 128),
    write_enabled=application.option_bool("rule_write_enabled", True),
    require_paused_create=application.option_bool("rule_create_paused_required", True),
)
semantic_metric_comparison = SemanticMetricComparisonExecutor(application.fallback)
semantic_read_intents = install_semantic_read_pipeline(
    application,
    semantic_metric_comparison,
    timeout_seconds=float(application.OPTIONS.get("semantic_intent_timeout_seconds") or 5),
    cache_ttl_seconds=float(application.OPTIONS.get("semantic_intent_cache_seconds") or 300),
)
install_ai_evidence_domains()
if application.option_bool("hybrid_assistant_mode_enabled", True):
    install_hybrid_assistant_query_policy()
ai_evidence_planner = install_ai_evidence_planner(
    application,
    device_index,
    home_snapshot,
    semantic_metric_comparison,
    enabled=application.option_bool("ai_evidence_planner_enabled", True),
    prefer_cloud=application.option_bool("ai_evidence_planner_prefer_cloud", True),
    max_rounds=int(application.OPTIONS.get("ai_evidence_planner_max_rounds") or 2),
    plan_timeout_seconds=float(application.OPTIONS.get("ai_evidence_planner_plan_timeout_seconds") or 12),
    synthesis_timeout_seconds=float(application.OPTIONS.get("ai_evidence_planner_synthesis_timeout_seconds") or 20),
    max_inventory_items=int(application.OPTIONS.get("ai_evidence_planner_max_inventory_items") or 120),
)
hybrid_verified_reads = install_hybrid_verified_read_routes(application, semantic_metric_comparison)
if application.option_bool("unified_mcp_agent_enabled", True):
    install_unified_mcp_agent_orchestrator(application)
install_explicit_hub_backup_workflow(application, automation_rule_workflow)
# Keep explicit named-rule writes outside AI and device-control wrappers. Exact
# normalized names or Rule IDs execute directly; uncertain targets never write.
named_rule_controller = install_named_rule_controller(application)
# Install authoritative health/attention routes outside every AI wrapper so their
# live classifications are terminal and cannot be reinterpreted by model synthesis.
install_device_health_fast_route(application)
install_automation_recommendation_terminal_route(application, automation_recommendation)
install_ollama_help_terminal_route(application)
# Hub restart is a destructive two-turn operation. Keep its pending confirmation
# outside AI and every generic protocol-follow-up route.
hub_restart_workflow = install_hub_restart_workflow(
    application,
    ttl_seconds=float(application.OPTIONS.get("hub_restart_confirmation_ttl_seconds") or 120),
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
install_device_refresh_webui(device_intelligence_webui_module)
install_device_intelligence_api(application, device_index)
install_mcp_tool_catalogue(application, application.mcp)
request_registry = install_cancellable_ask(application)
application.VERSION = RELEASE_VERSION
application.app.version = RELEASE_VERSION
install_automation_recommendation_webui(device_intelligence_webui_module)
install_clipboard_safe_webui(device_intelligence_webui_module)
install_http_safe_webui(device_intelligence_webui_module)
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
