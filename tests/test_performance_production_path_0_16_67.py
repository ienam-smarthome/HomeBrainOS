from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


from observed_agent_outcome import ObservedAgentOutcome  # noqa: E402
from performance_api_finalizer import finalize_performance_api_outcome  # noqa: E402


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
        "summary": "object fields: uptime, snapshot, deviceSummary, deviceStats, appSummary, appStats",
    }


class _FakeResult:
    def __init__(self, *, text: str = "", data=None) -> None:
        self.text = text
        self.data = data


class _FakeMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name: str, arguments: dict):
        self.calls.append((name, arguments))
        return _FakeResult(
            text=(
                "WARN SenseCap D1 Settings HTTP 408 while publishing state\n"
                "INFO Hallway motion active"
            ),
            data={"rows": 2},
        )


class _FakeAgent:
    def __init__(self) -> None:
        self.chat_calls = 0

    @staticmethod
    def _tool_succeeded(result) -> bool:
        return True

    async def _chat(self, messages, tools):
        self.chat_calls += 1
        return {
            "content": (
                "**Database:** Lean. At 187MB, your database is small and unlikely to be causing any performance drag. "
                "Hypothesis: This is likely caused by the driver attempting to communicate over a network timeout. "
                "These recurring sessionTick tasks increase the baseline CPU load. "
                "Resolve the NETWORK_BACKUP_FAILED alert immediately to prevent data loss. "
                "Increase the sessionTick interval to reduce scheduled jobs."
            )
        }


@pytest.mark.asyncio
async def test_api_finalizer_reads_logs_and_fail_closes_semantics() -> None:
    outcome = ObservedAgentOutcome(
        message=(
            "**Database:** Lean. At 187MB, your database is small and unlikely to be causing any performance drag. "
            "Hypothesis: This is likely caused by the driver attempting to communicate over a network timeout. "
            "These recurring sessionTick tasks increase the baseline CPU load. "
            "Resolve the NETWORK_BACKUP_FAILED alert immediately to prevent data loss. "
            "Increase the sessionTick interval to reduce scheduled jobs."
        ),
        request_class="live-read",
        evidence=[_performance_receipt()],
        choices=[],
        metrics={
            "outcome": "success",
            "counters": {"tool_calls": 3, "model_rounds": 2},
            "timings_ms": {},
        },
    )
    agent = _FakeAgent()
    mcp = _FakeMCP()

    finalized = await finalize_performance_api_outcome(
        agent,
        mcp,
        outcome,
        "Analyse my Hubitat performance and recommend improvements.",
    )

    assert mcp.calls == [
        (
            "hub_manage_logs",
            {"tool": "hub_get_logs", "args": {"since": "30m", "limit": 100}},
        )
    ]
    assert any(
        row.get("sub_tool") == "hub_get_logs" and row.get("success") is True
        for row in finalized.evidence
    )
    counters = finalized.metrics["counters"]
    assert counters["broad_performance_log_api_attempt"] == 1
    assert counters["broad_performance_log_api_success"] == 1
    assert counters["tool_calls"] == 4
    assert counters["model_rounds"] >= 3
    assert "performance_api_finalize" in finalized.metrics["timings_ms"]

    message = finalized.message
    assert "Database:** Lean" not in message
    assert "likely caused by" not in message
    assert "increase the baseline CPU load" not in message
    assert "prevent data loss" not in message
    assert "Increase the sessionTick interval" not in message


@pytest.mark.asyncio
async def test_actual_agent_request_calls_production_finalizer(monkeypatch) -> None:
    import app as production_app

    called: list[tuple[object, object, object, str]] = []
    original = ObservedAgentOutcome(
        message="provider draft",
        request_class="live-read",
        evidence=[_performance_receipt()],
        choices=[],
        metrics={"outcome": "success", "counters": {}, "timings_ms": {}},
    )

    async def fake_process_user_request_result(*args, **kwargs):
        return original

    async def fake_finalize(agent, mcp, outcome, prompt):
        called.append((agent, mcp, outcome, prompt))
        outcome.message = "production finalized"
        outcome.evidence = [
            *outcome.evidence,
            {
                "tool": "hub_manage_logs",
                "sub_tool": "hub_get_logs",
                "success": True,
                "arguments": {
                    "tool": "hub_get_logs",
                    "args": {"since": "30m", "limit": 100},
                },
            },
        ]
        return outcome

    monkeypatch.setattr(
        production_app.agent,
        "process_user_request_result",
        fake_process_user_request_result,
    )
    monkeypatch.setattr(
        production_app,
        "finalize_performance_api_outcome",
        fake_finalize,
    )

    request = production_app.ChatRequest(
        prompt="Analyse my Hubitat performance and recommend improvements.",
        session_id="performance-production-test",
    )
    result = await production_app._answer_result(request, connection=None)

    assert result.message == "production finalized"
    assert len(called) == 1
    assert called[0][0] is production_app.agent
    assert called[0][1] is production_app.mcp
    assert called[0][2] is original
    assert called[0][3] == request.message
    assert any(row.get("sub_tool") == "hub_get_logs" for row in result.evidence)


def test_app_source_wires_finalizer_without_sitecustomize() -> None:
    source = (APP_DIR / "app.py").read_text(encoding="utf-8")
    assert "from performance_api_finalizer import finalize_performance_api_outcome" in source
    assert "return await finalize_performance_api_outcome(" in source
    assert not (APP_DIR / "sitecustomize.py").exists()
