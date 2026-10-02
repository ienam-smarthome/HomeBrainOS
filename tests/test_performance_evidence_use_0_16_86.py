from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from evidence_recorder import EvidenceRecorder  # noqa: E402
from performance_diagnostic_evidence_gate import classify_adaptive_diagnostics  # noqa: E402
from performance_evidence_use_guard import guard_direct_performance_evidence_use  # noqa: E402
from performance_host_plan import collect_broad_performance_outcome, select_adaptive_log_targets  # noqa: E402
from synthesis_validator import validate_synthesis  # noqa: E402


def _nest_evidence() -> list[dict]:
    durations = (166621, 176938, 186138, 128959, 300568, 401699)
    return [
        {
            "tool": "hub_manage_logs",
            "sub_tool": "hub_get_logs",
            "success": True,
            "evidence_kind": "host_planned_performance_diagnostic",
            "arguments": {
                "tool": "hub_get_logs",
                "args": {"deviceId": "7934", "since": "6h", "limit": 120},
            },
            "details": {
                "logCount": 72,
                "logs": [
                    {
                        "date": f"2026-10-01 17:04:{index:02d}.000",
                        "level": "WARN",
                        "message": (
                            "dev|7934|Google Nest Hub|method runQ of child device Google Nest Hub "
                            f"ran for {duration:,}ms"
                        ),
                    }
                    for index, duration in enumerate(durations)
                ],
                "adaptiveTarget": {
                    "kind": "device",
                    "id": "7934",
                    "name": "Google Nest Hub",
                    "selectionSource": "hub_get_performance_stats",
                    "selectedFromExactRow": True,
                    "performanceRow": {
                        "id": "7934",
                        "name": "Google Nest Hub",
                        "pctBusy": 81.2,
                        "pctTotal": 23.747,
                        "averageMs": 1125.28,
                    },
                },
            },
        }
    ]


def test_comma_formatted_long_runq_warns_are_diagnostic_signals() -> None:
    targets = classify_adaptive_diagnostics(_nest_evidence())
    assert len(targets) == 1
    target = targets[0]
    assert target["classification"] == "diagnostic_signal"
    assert 166621 in target["longCallMs"]
    assert 401699 in target["longCallMs"]


def test_long_running_operation_is_not_promoted_to_network_cause() -> None:
    message = """### Diagnostic Hypotheses
**1. Google Nest Hub**
* **Hypothesis:** The long runQ calls suggest network connectivity or API response latency.
"""
    corrected, changed = guard_direct_performance_evidence_use(message, _nest_evidence())
    assert changed is True
    assert "long-running/stalled-operation hypothesis" in corrected
    assert "does not establish a network/connectivity cause" in corrected
    assert "API response latency" not in corrected

    final, issues = validate_synthesis(message, _nest_evidence())
    assert "performance_evidence_first" in issues
    assert "long-running/stalled-operation hypothesis" in final
    assert "does not establish a network/connectivity cause" in final


class _Metrics:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}

    def increment(self, name: str, amount: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + amount


class _Passthrough:
    async def run(self, operation, **_kwargs):
        return await operation()


class _Direct:
    async def run(self, operation, **_kwargs):
        return SimpleNamespace(message=await operation())


class _ProvenanceExecutor:
    def __init__(self, performance_data: dict) -> None:
        self.performance_data = performance_data
        self.evidence = EvidenceRecorder()
        self.calls: list[dict] = []

    @staticmethod
    def result_details(result):
        data = getattr(result, "data", None)
        if isinstance(data, dict) and isinstance(data.get("logs"), list):
            return {"logCount": len(data["logs"]), "logs": data["logs"]}
        return None

    @staticmethod
    def result_summary(result):
        data = getattr(result, "data", None)
        if isinstance(data, dict):
            return "object fields: " + ", ".join(data.keys())
        return "result"

    async def execute(self, gateway, arguments, **kwargs):
        self.calls.append(arguments)
        tool = arguments.get("tool")
        if tool == "hub_get_performance_stats":
            data = self.performance_data
        elif tool == "hub_get_logs" and (
            arguments.get("args", {}).get("deviceId")
            or arguments.get("args", {}).get("appId")
        ):
            data = {"logs": []}
        else:
            data = {}
        return SimpleNamespace(
            success=True,
            elapsed_ms=1,
            effect="read",
            result=SimpleNamespace(data=data),
        )


class _Agent:
    def __init__(self, performance_data: dict) -> None:
        self.request_metrics = _Metrics()
        self.executor = _ProvenanceExecutor(performance_data)
        self.direct_outcomes = _Direct()
        self.request_observation = _Passthrough()


def test_near_threshold_busy_app_can_win_and_exact_row_is_preserved() -> None:
    performance_data = {
        "deviceStats": [],
        "appStats": [
            {
                "id": "4129",
                "name": "SenseCap D1 Settings",
                "pctBusy": 18.8,
                "pctTotal": 0.992,
                "averageMs": 400.0,
                "count": 5042,
            },
            {
                "id": "3919",
                "name": "Slow Diagnostic App",
                "pctBusy": 1.0,
                "pctTotal": 0.2,
                "averageMs": 5200.0,
            },
        ],
    }
    selected = select_adaptive_log_targets(performance_data)
    assert selected == [{"kind": "app", "id": "4129", "name": "SenseCap D1 Settings"}]

    agent = _Agent(performance_data)
    token = agent.executor.evidence.begin()
    try:
        asyncio.run(
            collect_broad_performance_outcome(
                agent,
                "Analyse my Hubitat performance and recommend improvements.",
            )
        )
        receipts = agent.executor.evidence.receipts()
    finally:
        agent.executor.evidence.reset(token)

    adaptive = [
        row for row in receipts
        if row.get("evidence_kind") == "host_planned_performance_diagnostic"
    ]
    assert len(adaptive) == 1
    assert adaptive[0]["arguments"]["args"]["appId"] == "4129"
    target = adaptive[0]["details"]["adaptiveTarget"]
    assert target["id"] == "4129"
    assert target["name"] == "SenseCap D1 Settings"
    assert target["selectedFromExactRow"] is True
    assert target["selectionSource"] == "hub_get_performance_stats"
    assert target["performanceRow"]["pctBusy"] == 18.8
    assert target["performanceRow"]["count"] == 5042


def _mcp_warning_evidence() -> list[dict]:
    return [
        {
            "tool": "hub_manage_logs",
            "sub_tool": "hub_get_logs",
            "success": True,
            "evidence_kind": "host_planned_performance_source",
            "arguments": {"tool": "hub_get_logs", "args": {"since": "30m", "limit": 100}},
            "details": {
                "logCount": 1,
                "logs": [
                    {
                        "date": "2026-10-01 17:04:05.101",
                        "level": "WARN",
                        "message": (
                            'app|4151|MCP Rule Server|[MCP1] {"entry":{"component":"hub-admin",'
                            '"level":"warn","message":"[hubrt] slow internal GET /logs/json took 8112ms"}}'
                        ),
                    }
                ],
            },
        }
    ]


def test_literal_mcp_warning_survives_final_semantic_stack() -> None:
    message = (
        "* **MCP Rule Server (ID 4151):** A WARN log was observed. The returned activity is "
        "worth reviewing; this turn does not establish material background overhead, log growth, "
        "or slower history lookups from that activity."
    )
    corrected, issues = validate_synthesis(message, _mcp_warning_evidence())
    assert "performance_evidence_first" in issues or "performance_log_observation" in issues
    assert "slow internal GET /logs/json took 8112ms" in corrected
    assert "returned activity is worth reviewing" not in corrected.casefold()


def test_same_second_cluster_tuning_is_inspection_first() -> None:
    evidence = [
        {
            "tool": "hub_manage_logs",
            "sub_tool": "hub_get_logs",
            "success": True,
            "evidence_kind": "host_planned_performance_source",
            "arguments": {"tool": "hub_get_logs", "args": {"since": "30m", "limit": 100}},
            "details": {
                "hostDerivedTiming": {
                    "sameSecondClusters": [
                        {
                            "second": "2026-10-01 17:04:03",
                            "rowCount": 24,
                            "distinctSourceCount": 13,
                            "spanMs": 390,
                        }
                    ]
                }
            },
        }
    ]
    message = (
        "2. **Review Octopus Meter Configuration:** Determine if the same-second clustered "
        "reporting can be staggered or if the frequency should be reduced."
    )
    corrected, changed = guard_direct_performance_evidence_use(message, evidence)
    assert changed is True
    assert "can be staggered" not in corrected
    assert "whether update scheduling/reporting is configurable" in corrected
    assert "changing frequency is necessary" in corrected
