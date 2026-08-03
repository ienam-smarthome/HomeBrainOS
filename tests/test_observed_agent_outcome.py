from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import AgentOutcome  # noqa: E402
from observed_agent_outcome import (  # noqa: E402
    ObservedAgentOutcome,
    build_observed_agent_outcome,
)


def test_builder_preserves_complete_base_outcome_contract() -> None:
    evidence = [{"tool": "hub_read_devices", "success": True}]
    choices = ["Hallway Light", "Landing Light"]
    metrics = {
        "outcome": "unresolved",
        "counters": {"device_resolution_ambiguous": 1},
        "timings_ms": {"total": 42},
    }
    base = AgentOutcome(
        message="Choose one device.",
        request_class="live-read",
        evidence=evidence,
        choices=choices,
        confirmation_required=True,
        confirmation_count=2,
    )

    observed = build_observed_agent_outcome(base, metrics)

    assert isinstance(observed, ObservedAgentOutcome)
    assert observed.message == base.message
    assert observed.request_class == base.request_class
    assert observed.evidence is evidence
    assert observed.choices is choices
    assert observed.confirmation_required is True
    assert observed.confirmation_count == 2
    assert observed.metrics is metrics


def test_observed_outcome_keeps_empty_metrics_default() -> None:
    outcome = ObservedAgentOutcome(
        message="Done.",
        request_class="live-read",
        evidence=[],
        choices=[],
    )

    assert outcome.metrics == {}
