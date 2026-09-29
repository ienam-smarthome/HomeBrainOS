from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _performance_receipt() -> dict:
    return {
        "tool": "hub_manage_logs",
        "sub_tool": "hub_get_performance_stats",
        "success": True,
        "supports_live_claim": True,
        "evidence_kind": "tool_result",
        "arguments": {
            "tool": "hub_get_performance_stats",
            "args": {"type": "both"},
        },
    }


def test_sitecustomize_installs_performance_completion_router() -> None:
    import mcp_agent_orchestrator

    importlib.import_module("sitecustomize")

    assert getattr(
        mcp_agent_orchestrator.UnifiedMCPAgent,
        "_performance_completion_router_01666",
        False,
    ) is True
    source = Path(APP_DIR / "sitecustomize.py").read_text(encoding="utf-8")
    assert "hub_get_performance_stats" in source
    assert "return await self._final_answer(messages)" in source
    assert "hub_get_logs" in source


def test_serializer_backstop_repairs_exact_01665_failure_without_logs() -> None:
    importlib.import_module("sitecustomize")
    import api_response_builder

    outcome = SimpleNamespace(
        message=(
            "**Database:** Lean. At 182MB, your database is small and unlikely to be causing any performance drag. "
            "Hypothesis: This is likely caused by the driver attempting to communicate over a network timeout. "
            "These recurring sessionTick tasks increase the baseline CPU load. "
            "Resolve the NETWORK_BACKUP_FAILED alert immediately to prevent data loss. "
            "Increase the sessionTick interval to reduce scheduled jobs."
        ),
        evidence=[_performance_receipt()],
        metrics={"outcome": "success", "counters": {}, "timings_ms": {}},
        route="unified-mcp-agent",
        request_class="live-read",
        choices=[],
        confirmation_required=False,
        confirmation_count=0,
        automation_items=[],
    )

    response = api_response_builder.build_agent_response(
        outcome,
        model="gemma4:31b",
        elapsed_ms=1,
        version="0.16.66",
    )
    message = response["message"]

    assert "Database:** Lean" not in message
    assert "likely caused by" not in message
    assert "increase the baseline CPU load" not in message
    assert "prevent data loss" not in message
    assert "Increase the sessionTick interval" not in message
