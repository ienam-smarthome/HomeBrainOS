from __future__ import annotations

import asyncio

import uvicorn

import app as application
from cancellable_requests import install_cancellable_ask
from dashboard_api import install_dashboard_api
from fast_fallback_extended_reads import FastFallbackRouter
from fastpath_ai_handoff import install_fastpath_ai_handoff
from mcp_state_broker import MCPStateBroker
from mcp_tool_catalogue import install_mcp_tool_catalogue
from ollama_agent_adaptive import AdaptiveFinalAnswerAgent
from request_tracing import install_request_tracing


RELEASE_VERSION = "0.3.4-alpha"


def _replace_mcp_client() -> None:
    options = application.OPTIONS
    application.mcp = MCPStateBroker(
        application.mcp,
        device_ttl_seconds=float(
            options.get("mcp_device_cache_seconds") or 12
        ),
        catalog_ttl_seconds=float(
            options.get("mcp_catalog_cache_seconds") or 60
        ),
        hub_ttl_seconds=float(options.get("mcp_hub_cache_seconds") or 20),
    )


def _replace_fallback_router() -> None:
    application.fallback = FastFallbackRouter(
        application.mcp,
        attention_stale_hours=float(
            application.OPTIONS.get("attention_stale_hours") or 48
        ),
        cpu_probe_enabled=application.option_bool("hub_cpu_probe_enabled", True),
        cpu_probe_timeout_seconds=float(
            application.OPTIONS.get("hub_cpu_probe_timeout_seconds") or 2.5
        ),
    )


def _replace_ollama_agent() -> None:
    previous = application.ollama
    options = application.OPTIONS

    application.ollama = AdaptiveFinalAnswerAgent(
        client=application.mcp,
        base_url=str(options.get("ollama_base_url") or ""),
        model=str(options.get("ollama_model") or ""),
        planner_model=str(options.get("ollama_planner_model") or ""),
        routine_model=str(options.get("ollama_routine_model") or ""),
        health_timeout_seconds=float(
            options.get("ollama_health_timeout_seconds") or 3
        ),
        planner_timeout_seconds=max(
            35.0,
            float(options.get("ollama_planner_timeout_seconds") or 35),
        ),
        response_timeout_seconds=float(
            options.get("ollama_response_timeout_seconds") or 75
        ),
        routine_response_timeout_seconds=float(
            options.get("ollama_routine_response_timeout_seconds") or 40
        ),
        num_ctx=int(options.get("ollama_num_ctx") or 4096),
        num_predict=int(options.get("ollama_num_predict") or 180),
        keep_alive=str(options.get("ollama_keep_alive") or "30m"),
        planner_tool_limit=int(options.get("ollama_planner_tool_limit") or 4),
        tool_result_limit_chars=int(
            options.get("ollama_tool_result_limit_chars") or 6000
        ),
        max_tool_rounds=int(options.get("ollama_max_tool_rounds") or 3),
        require_sensitive_confirmation=application.option_bool(
            "require_sensitive_confirmation",
            True,
        ),
        fallback_provider=application.fallback.answer,
        evidence_item_limit=int(options.get("ollama_evidence_item_limit") or 8),
    )

    try:
        asyncio.run(previous.close())
    except Exception:
        pass


_replace_mcp_client()
_replace_fallback_router()
_replace_ollama_agent()
install_fastpath_ai_handoff(application)
request_traces = install_request_tracing(
    application,
    application.mcp,
    limit=int(application.OPTIONS.get("request_trace_limit") or 20),
)
dashboard_snapshot = install_dashboard_api(
    application,
    ttl_seconds=float(application.OPTIONS.get("dashboard_refresh_seconds") or 30),
)
install_mcp_tool_catalogue(application, application.mcp)
request_registry = install_cancellable_ask(application)
application.VERSION = RELEASE_VERSION
application.app.version = RELEASE_VERSION
app = application.app


@app.on_event("shutdown")
async def cancel_active_requests() -> None:
    await request_registry.cancel_all()


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8788,
        log_level="info",
        proxy_headers=True,
    )
