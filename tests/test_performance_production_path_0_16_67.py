from __future__ import annotations

import sys
from pathlib import Path

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


from observed_agent_outcome import ObservedAgentOutcome  # noqa: E402
from performance_api_finalizer import (  # noqa: E402
    _append_packet,
    _consume_packet,
    finalize_performance_api_outcome,
)


def _receipt(sub_tool: str, *, gateway: str = "hub_manage_logs", details=None) -> dict:
    args = {"type": "both"} if sub_tool == "hub_get_performance_stats" else {}
    if sub_tool == "hub_get_logs":
        args = {"since": "30m", "limit": 100}
    row = {
        "tool": gateway,
        "sub_tool": sub_tool,
        "success": True,
        "supports_live_claim": True,
        "evidence_kind": "tool_result",
        "arguments": {"tool": sub_tool, **({"args": args} if args else {})},
        "summary": f"successful {sub_tool}",
    }
    if details is not None:
        row["details"] = details
    return row


def _performance_receipt() -> dict:
    return _receipt("hub_get_performance_stats")


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
            data={
                "logs": [
                    {"level": "WARN", "message": "SenseCap D1 Settings: No route to host"},
                    {"level": "WARN", "message": "Google TV Streamer ADB shell timeout"},
                ],
                "count": 2,
            }
        )


class _FakeAgent:
    def __init__(self, responses: list[str] | None = None) -> None:
        self.chat_calls = 0
        self.responses = list(responses or [])
        self.seen_messages: list[list[dict]] = []

    @staticmethod
    def _tool_succeeded(result) -> bool:
        return True

    async def _chat(self, messages, tools):
        self.chat_calls += 1
        self.seen_messages.append(messages)
        if self.responses:
            content = self.responses.pop(0)
        else:
            content = (
                "**Database:** Lean. At 187MB, your database is small and unlikely to be causing any performance drag. "
                "Hypothesis: This is likely caused by the driver attempting to communicate over a network timeout. "
                "These recurring sessionTick tasks increase the baseline CPU load. "
                "Resolve the NETWORK_BACKUP_FAILED alert immediately to prevent data loss. "
                "Increase the sessionTick interval to reduce scheduled jobs."
            )
        return {"content": content}


@pytest.mark.asyncio
async def test_api_finalizer_reads_logs_reuses_performance_and_fail_closes_semantics() -> None:
    _consume_packet()
    _append_packet(
        "hub_get_performance_stats",
        '{"result":{"uptime":"13h","snapshot":{"databaseSizeMB":187},"deviceStats":[{"name":"LG webOS TV","avgMs":3035}]}}',
    )
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
    assert not any(
        row.get("evidence_kind") == "performance_api_synthesis_snapshot"
        for row in finalized.evidence
    )
    counters = finalized.metrics["counters"]
    assert counters["broad_performance_log_api_attempt"] == 1
    assert counters["broad_performance_log_api_success"] == 1
    assert "performance_api_snapshot_success" not in counters
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
async def test_01669_reuses_all_measured_sources_and_rejects_false_no_evidence_answer() -> None:
    _consume_packet()
    _append_packet(
        "hub_get_metrics",
        '{"result":{"current":{"freeMemoryMb":993,"databaseSizeMB":187},"healthAlerts":[]}}',
    )
    _append_packet(
        "hub_get_performance_stats",
        '{"result":{"deviceStats":[{"name":"LG webOS TV","avgMs":3035}]}}',
    )
    _append_packet(
        "hub_get_jobs",
        '{"result":{"scheduledJobs":[{"name":"sessionTick"}]}}',
    )
    _append_packet(
        "hub_get_logs",
        '{"result":{"logs":[{"level":"WARN","message":"SenseCap D1 Settings: No route to host"}]}}',
    )

    original = (
        "At 187MB the database is small and unlikely to be causing any performance drag. "
        "LG webOS TV averages 3,035ms. There are 219 scheduled jobs. "
        "Resolve NETWORK_BACKUP_FAILED immediately to prevent data loss."
    )
    outcome = ObservedAgentOutcome(
        message=original,
        request_class="live-read",
        evidence=[
            _receipt("hub_get_metrics", gateway="hub_read_diagnostics"),
            _receipt("hub_get_performance_stats"),
            _receipt("hub_get_jobs"),
            _receipt(
                "hub_get_logs",
                details={
                    "logCount": 2,
                    "logs": [
                        {"level": "WARN", "message": "SenseCap D1 Settings: No route to host"},
                        {"level": "WARN", "message": "Google TV Streamer ADB shell timeout"},
                    ],
                },
            ),
        ],
        choices=[],
        metrics={
            "outcome": "success",
            "counters": {"tool_calls": 4, "model_rounds": 2},
            "timings_ms": {},
        },
    )
    denial = (
        "The available evidence from the current turn does not establish any facts "
        "regarding your Hubitat performance, as no MCP tools were executed in this turn."
    )
    agent = _FakeAgent([denial])
    mcp = _FakeMCP()

    finalized = await finalize_performance_api_outcome(
        agent,
        mcp,
        outcome,
        "Analyse my Hubitat performance and recommend improvements.",
    )

    assert mcp.calls == []
    flattened = "\n".join(
        str(message.get("content") or "")
        for call in agent.seen_messages
        for message in call
    )
    assert "993" in flattened
    assert "3035" in flattened
    assert "sessionTick" in flattened
    assert "SenseCap D1 Settings" in flattened
    assert "no MCP tools were executed" not in finalized.message
    assert "3,035ms" in finalized.message
    assert finalized.metrics["counters"]["performance_api_false_evidence_fallback"] == 1
    assert "performance_api_snapshot_success" not in finalized.metrics["counters"]
    assert finalized.metrics["counters"]["broad_performance_log_api_reused"] == 1


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


def test_app_source_wires_finalizer_without_sitecustomize() -> None:
    source = (APP_DIR / "app.py").read_text(encoding="utf-8")
    assert "from performance_api_finalizer import finalize_performance_api_outcome" in source
    assert "return await finalize_performance_api_outcome(" in source
    assert not (APP_DIR / "sitecustomize.py").exists()
