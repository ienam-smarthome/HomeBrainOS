from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from route_catalogue import build_route_registry  # noqa: E402
from unified_routing_arbiter import UnifiedRoutingArbiter  # noqa: E402


FIXED_ROUTING_EVAL = (
    (
        "Turn on Kitchen Lamp",
        "control",
        "device.control",
        {"success", "route", "message"},
    ),
    (
        "Which rooms are active?",
        "deterministic-read",
        "home.active-rooms",
        {"success", "route", "message", "display"},
    ),
    (
        "Check logs to see if there are any issues",
        "diagnostics",
        "diagnostics.hub-logs",
        {"success", "route", "message", "display"},
    ),
    (
        "Why might the house feel uncomfortable this evening?",
        "open-ended",
        None,
        {"success", "route", "message", "tools_used"},
    ),
)


def test_four_tier_fixed_routing_eval_set():
    arbiter = UnifiedRoutingArbiter(build_route_registry())

    for query, expected_tier, expected_capability, answer_shape in FIXED_ROUTING_EVAL:
        interpretation = arbiter.interpret(query)
        assert interpretation.intent_tier == expected_tier, query
        if expected_capability is not None:
            assert interpretation.capability_id == expected_capability, query
        assert interpretation.confidence > 0
        assert answer_shape >= {"success", "route", "message"}


def test_routing_interpretation_is_structured_not_a_free_text_tool_name():
    interpretation = UnifiedRoutingArbiter(build_route_registry()).interpret(
        "Check logs for errors"
    )

    payload = interpretation.response_dict()
    assert payload == {
        "capability_id": "diagnostics.hub-logs",
        "intent_tier": "diagnostics",
        "slots": {},
        "confidence": 1.0,
        "reason": interpretation.reason,
    }
    assert "hub_get_logs" not in payload.values()
