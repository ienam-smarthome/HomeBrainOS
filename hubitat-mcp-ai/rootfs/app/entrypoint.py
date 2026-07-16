from __future__ import annotations

import asyncio

import uvicorn

import app as application
from ollama_agent_natural import NaturalHubitatOllamaAgent


RELEASE_VERSION = "0.2.2-alpha"


def _replace_ollama_agent() -> None:
    previous = application.ollama
    options = application.OPTIONS

    application.ollama = NaturalHubitatOllamaAgent(
        client=application.mcp,
        base_url=str(options.get("ollama_base_url") or ""),
        model=str(options.get("ollama_model") or ""),
        planner_model=str(options.get("ollama_planner_model") or ""),
        routine_model=str(options.get("ollama_routine_model") or ""),
        health_timeout_seconds=float(
            options.get("ollama_health_timeout_seconds") or 3
        ),
        planner_timeout_seconds=float(
            options.get("ollama_planner_timeout_seconds") or 45
        ),
        response_timeout_seconds=float(
            options.get("ollama_response_timeout_seconds") or 90
        ),
        routine_response_timeout_seconds=float(
            options.get("ollama_routine_response_timeout_seconds") or 55
        ),
        num_ctx=int(options.get("ollama_num_ctx") or 4096),
        num_predict=int(options.get("ollama_num_predict") or 220),
        keep_alive=str(options.get("ollama_keep_alive") or "30m"),
        planner_tool_limit=int(options.get("ollama_planner_tool_limit") or 6),
        tool_result_limit_chars=int(
            options.get("ollama_tool_result_limit_chars") or 12000
        ),
        max_tool_rounds=int(options.get("ollama_max_tool_rounds") or 3),
        require_sensitive_confirmation=application.option_bool(
            "require_sensitive_confirmation",
            True,
        ),
        fallback_provider=application.fallback.answer,
        evidence_item_limit=int(options.get("ollama_evidence_item_limit") or 10),
    )

    # app.py constructs the legacy agent while loading its routes. Close that
    # unused HTTP client before serving requests, then let the existing shutdown
    # handler close the replacement agent.
    try:
        asyncio.run(previous.close())
    except Exception:
        pass


_replace_ollama_agent()
application.VERSION = RELEASE_VERSION
application.app.version = RELEASE_VERSION
app = application.app


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8788,
        log_level="info",
        proxy_headers=True,
    )
