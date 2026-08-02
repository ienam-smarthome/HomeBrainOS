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


def test_builder_preserves_existing_contract_and_adds_metrics() -> None:
    response = build_agent_response(
        FakeOutcome(),
        model="gemma4:31b",
        elapsed_ms=1532,
        version="0.10.294",
    )

    assert response["success"] is True
    assert response["route"] == "unified-mcp-agent"
    assert response["request_class"] == "live-read"
    assert response["message"] == "Two lights are on."
    assert response["metrics"]["counters"]["model_rounds"] == 2
    assert response["elapsed_ms"] == 1532
    assert response["version"] == "0.10.294"


def test_builder_copies_mutable_evidence_and_metrics() -> None:
    outcome = FakeOutcome()
    response = build_agent_response(
        outcome,
        model="model",
        elapsed_ms=1,
        version="version",
    )

    response["evidence"][0]["tool"] = "changed"
    response["metrics"]["counters"]["tool_calls"] = 99

    assert outcome.evidence[0]["tool"] == "hub_read_devices"
    assert outcome.metrics["counters"]["tool_calls"] == 1


def test_builder_handles_legacy_outcome_without_metrics() -> None:
    class LegacyOutcome:
        message = "Done."
        request_class = "write"
        evidence: list[dict[str, Any]] = []
        choices: list[str] = []

    response = build_agent_response(
        LegacyOutcome(),
        model="model",
        elapsed_ms=-4,
        version="dev",
    )

    assert response["metrics"] == {}
    assert response["confirmation_required"] is False
    assert response["confirmation_count"] == 0
    assert response["elapsed_ms"] == 0


def test_builder_does_not_add_prompt_or_session_fields() -> None:
    response = build_agent_response(
        FakeOutcome(),
        model="model",
        elapsed_ms=2,
        version="dev",
    )

    assert "prompt" not in response
    assert "query" not in response
    assert "session_id" not in response
    assert "request_id" not in response
