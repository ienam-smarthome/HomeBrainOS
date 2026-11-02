"""Regression for 0.18.366 live crash on source-choice checkpoint metrics.

The model's no-tool source follow-up previously raised:
ValueError: Unsupported metric counter: investigation_source_checkpoint_offered
because both branches of its conditional metric call were omitted from the
allowlist and invisible to the old literal-only source scanner.
No Hubitat or model is called by these tests.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from evidence_first_checkpoint_plan import SourceCheckpointBudget  # noqa: E402
from request_metrics import RequestMetrics, increment_active_metric  # noqa: E402


def _observed_read(tool="hub_read_apps_code", app_id="42"):
    return {
        "tool": tool,
        "arguments": {"tool": "hub_get_app_config", "args": {"appId": app_id}},
        "success": True, "effect": "read", "mutates": False,
    }


def test_live_checkpoint_offer_and_suppression_are_safe_request_metrics():
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        gate = SourceCheckpointBudget(max_offers=3)
        receipts = [_observed_read()]
        for kind, snapshot in [
            ("configuration-semantics", receipts),
            ("upstream-input", receipts),  # no fresh evidence: suppressed
            ("target-history", [*receipts, _observed_read(app_id="43")]),
            ("issuer-decision", [*receipts, _observed_read(app_id="43")]),
            ("diagnostic-discriminator", [*receipts, _observed_read(app_id="43"),
                                           _observed_read(app_id="44")]),
            ("missing-required-source", [*receipts, _observed_read(app_id="43"),
                                          _observed_read(app_id="44"),
                                          _observed_read(app_id="45")]),
        ]:
            allowed = gate.offer(kind, snapshot)
            # Exact expression used by mcp_agent_orchestrator.
            increment_active_metric(
                "investigation_source_checkpoint_offered" if allowed
                else "investigation_source_checkpoint_suppressed"
            )
        counters = metrics.snapshot()["counters"]
        assert counters == {
            "investigation_source_checkpoint_offered": 3,
            "investigation_source_checkpoint_suppressed": 3,
        }
        assert len(gate.offered_kinds) == 3
    finally:
        metrics.reset(token)


def test_conditional_source_metric_callsite_remains_contract_scannable():
    path = APP / "mcp_agent_orchestrator.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "increment_active_metric":
            continue
        arg = node.args[0]
        if not isinstance(arg, ast.IfExp):
            continue
        if all(isinstance(branch, ast.Constant) and isinstance(branch.value, str)
               for branch in (arg.body, arg.orelse)):
            candidates = {arg.body.value, arg.orelse.value}
            if "investigation_source_checkpoint_offered" in candidates:
                hits.append(candidates)
    assert hits == [{
        "investigation_source_checkpoint_offered",
        "investigation_source_checkpoint_suppressed",
    }]
    assert all(name in RequestMetrics.ALLOWED_COUNTERS for name in hits[0])


@pytest.mark.parametrize("name", [
    "investigator_producer_config_read",
    "investigator_archived_producer_log_read",
])
def test_injected_investigation_metric_callback_is_registered(name):
    # Several source-follow-up functions receive increment_active_metric
    # under an injected callback name; literal-only scans missed that path.
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        increment_active_metric(name)
        assert metrics.snapshot()["counters"][name] == 1
    finally:
        metrics.reset(token)


def test_metric_allowlist_still_rejects_private_dynamic_names():
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        with pytest.raises(ValueError, match="Unsupported metric counter"):
            increment_active_metric("internal:appId=42")
    finally:
        metrics.reset(token)
