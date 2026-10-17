from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from api_response_builder import build_agent_response  # noqa: E402


@dataclass
class FakeOutcome:
    message: str = "Two lights are on."
    request_class: str = "live-read"
    evidence: list[dict[str, Any]] = field(
        default_factory=lambda: [{"tool": "hub_read_devices", "success": True}]
    )
    choices: list[str] = field(default_factory=list)
    confirmation_required: bool = False
    confirmation_count: int = 0
    metrics: dict[str, Any] = field(
        default_factory=lambda: {
            "outcome": "success",
            "counters": {"model_rounds": 2, "tool_calls": 1},
            "timings_ms": {"provider": 1200, "total": 1500},
        }
    )


def test_builder_preserves_contract_and_adds_metric_rows() -> None:
    response = build_agent_response(
        FakeOutcome(), model="gemma4:31b", elapsed_ms=1532, version="0.10.298"
    )

    assert response["success"] is True
    assert response["route"] == "unified-mcp-agent"
    assert response["request_class"] == "live-read"
    assert response["message"] == "Two lights are on."
    assert response["metrics"]["counters"]["model_rounds"] == 2
    assert response["model"] == "gemma4:31b"
    assert response["metric_rows"] == [
        {"label": "Model rounds", "value": "2"},
        {"label": "Tool calls", "value": "1"},
        {"label": "Provider", "value": "1.2 s"},
        {"label": "Agent phase", "value": "1.5 s"},
        {"label": "Outcome", "value": "success"},
    ]
    assert response["outcome_presentation"] == {
        "value": "success",
        "label": "Success",
        "tone": "positive",
    }
    assert response["elapsed_ms"] == 1532


def test_builder_omits_model_when_no_model_round_participated() -> None:
    outcome = FakeOutcome()
    outcome.metrics = {
        "outcome": "success",
        "counters": {"tool_calls": 1},
        "timings_ms": {"total": 900},
    }

    response = build_agent_response(
        outcome, model="gemma4:31b", elapsed_ms=900, version="dev"
    )

    assert response["model"] is None
    assert all(row["label"] != "Model rounds" for row in response["metric_rows"])


def test_builder_copies_mutable_evidence_and_metrics() -> None:
    outcome = FakeOutcome()
    response = build_agent_response(outcome, model="model", elapsed_ms=1, version="dev")
    response["evidence"][0]["tool"] = "changed"
    response["metrics"]["counters"]["tool_calls"] = 99
    response["outcome_presentation"]["label"] = "Changed"
    assert outcome.evidence[0]["tool"] == "hub_read_devices"
    assert outcome.metrics["counters"]["tool_calls"] == 1


def test_builder_handles_legacy_outcome_without_metrics() -> None:
    class LegacyOutcome:
        message = "Done."
        request_class = "write"
        evidence: list[dict[str, Any]] = []
        choices: list[str] = []

    response = build_agent_response(
        LegacyOutcome(), model="model", elapsed_ms=-4, version="dev"
    )
    assert response["metrics"] == {}
    assert response["metric_rows"] == []
    assert response["outcome_presentation"] is None
    assert response["confirmation_required"] is False
    assert response["confirmation_count"] == 0
    assert response["elapsed_ms"] == 0
    assert response["model"] == "model"


def test_builder_exposes_each_supported_outcome_without_message_inspection() -> None:
    expected = {
        "unresolved": ("Unresolved", "warning"),
        "refused": ("Refused", "warning"),
        "cancelled": ("Cancelled", "neutral"),
        "failed": ("Failed", "critical"),
    }
    for value, (label, tone) in expected.items():
        outcome = FakeOutcome(message="Arbitrary text")
        outcome.metrics["outcome"] = value
        response = build_agent_response(outcome, model="model", elapsed_ms=2, version="dev")
        assert response["outcome_presentation"] == {
            "value": value,
            "label": label,
            "tone": tone,
        }


def test_builder_does_not_add_prompt_or_session_fields() -> None:
    response = build_agent_response(
        FakeOutcome(), model="model", elapsed_ms=2, version="dev"
    )
    assert "prompt" not in response
    assert "query" not in response
    assert "session_id" not in response
    assert "request_id" not in response
    assert "Bedroom" not in repr(response["metric_rows"])


def test_builder_blocks_live_performance_log_causality_even_if_orchestrator_returns_draft() -> None:
    outcome = FakeOutcome(
        message=(
            "### Root Causes (from Logs)\n"
            "The logs reveal three specific patterns driving this load:\n\n"
            "1. **TV Power Trigger Loop**: Because the TV power is fluctuating slightly "
            "(e.g., 77W → 82W → 81W), the rule is constantly restarting. This is likely "
            "driving the high busy percentage for the LG TV.\n\n"
            "### Recommended Optimizations\n"
            "* **Fix the TV Rule**: Modify `Power saving: TV OFF (medium setting)`. "
            "Instead of triggering immediately at 65W, add a **stays that way for** "
            "duration of 1 minute."
        ),
        evidence=[
            {
                "tool": "hub_read_diagnostics",
                "sub_tool": "hub_get_performance_stats",
                "success": True,
                "arguments": {"tool": "hub_get_performance_stats"},
            },
            {
                "tool": "hub_read_diagnostics",
                "sub_tool": "hub_get_logs",
                "success": True,
                "arguments": {"tool": "hub_get_logs"},
                "details": {
                    "logs": [
                        {
                            "message": (
                                "app|2817|Power saving: TV OFF (medium setting)|"
                                "Triggered: Power level of TV(81) reported >= 65.0"
                            )
                        },
                        {
                            "message": (
                                "app|2817|Power saving: TV OFF (medium setting)|"
                                "Action: Wait for event: Power level of TV(81) is <= 50.0 "
                                "and stays that way for: 0:03:00"
                            )
                        },
                        {
                            "message": (
                                "app|2817|Power saving: TV OFF (medium setting)|"
                                "Event: TV power 81"
                            )
                        },
                        {
                            "message": (
                                "app|2817|Power saving: TV OFF (medium setting)|"
                                "Event: TV power 84"
                            )
                        },
                    ]
                },
            },
        ],
    )

    response = build_agent_response(
        outcome, model="gemma4:31b", elapsed_ms=1000, version="0.16.51"
    )
    message = response["message"]

    assert "Root Causes (from Logs)" not in message
    assert "not proven performance causes" in message
    assert "patterns driving this load" not in message
    assert "fluctuating slightly" not in message
    assert "stayed on one qualifying side of the threshold" in message
    assert "likely driving the high busy percentage" not in message
    assert "do not establish that it causes the measured performance result" in message
    assert "did not read the rule/app configuration" in message


def test_explicit_paid_mixed_rounds_show_local_budget_boundary_without_invoice_claim():
    outcome = FakeOutcome()
    outcome.metrics = {
        "outcome": "unresolved",
        "counters": {
            "paid_model_requested": 1,
            "paid_model_reserved": 6,
            "paid_routing_reservation_blocked": 3,
            "model_rounds": 9,
        },
        "timings_ms": {"total": 56000},
        "model_round_details": [
            *[{"model": "deepseek-v4-pro", "provider": "ollama-cloud"} for _ in range(6)],
            *[{"model": "gemma4:31b", "provider": "ollama-cloud"} for _ in range(3)],
        ],
        "paid_guard": {
            "status": "round_exceeds_budget",
            "configured_budget_usd": 3,
            "already_reserved_usd": 2.852,
            "estimated_round_usd": 0.1696,
        },
    }
    response = build_agent_response(outcome, model="gemma4:31b",
                                    elapsed_ms=56030, version="0.18.17")
    routing = response["paid_routing"]
    assert routing["used"] is True
    assert routing["paid_rounds"] == 6
    assert routing["free_rounds_after_paid"] == 3
    assert routing["mixed_models"] is True
    assert routing["estimated_budget_exhausted"] is True
    assert "reservations-not-provider-charges" in routing["accounting"]
    assert "6 recorded round(s)" in response["message"]
    assert "3 round(s)" in response["message"]
    assert "not an Ollama invoice" in response["message"]
    assert response["model"] == "gemma4:31b"


def test_paid_model_no_budget_exhaustion_never_warns_about_midway_switch():
    outcome = FakeOutcome()
    outcome.metrics["counters"]["paid_model_requested"] = 1
    outcome.metrics["model_round_details"] = [
        {"model": "deepseek-v4-pro", "provider": "ollama-cloud"},
        {"model": "gemma4:31b", "provider": "ollama-cloud"},
    ]
    response = build_agent_response(outcome, model="gemma4:31b",
                                    elapsed_ms=5000, version="0.18.17")
    assert response["paid_routing"]["paid_rounds"] == 1
    assert response["paid_routing"]["free_rounds_after_paid"] == 1
    assert response["paid_routing"]["estimated_budget_exhausted"] is False
    assert "**Model continuity:**" not in response["message"]
