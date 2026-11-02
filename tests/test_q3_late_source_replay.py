"""Same-input offline regression for Q3 post-grounding source selection.

Frozen admission/receipt scenarios are synthetic. This checks source-choice
equivalence only; it does not constitute a model, quality or latency benchmark.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))
from evidence_first_checkpoint_plan import SourceCheckpointBudget
from evidence_first_source_followup import (
    LATE_SOURCE_ORDER, ModelSourceFollowup, choose_model_source_followup,
)

FIXTURE = Path(__file__).parent / "fixtures" / "q3_late_source_replay_v1.json"
READ_GATEWAYS = (
    "hub_read_apps_code", "hub_read_rules", "hub_read_devices",
    "hub_read_diagnostics", "hub_search_tools",
)


def _init(case):
    budget = SourceCheckpointBudget(max_offers=3)
    receipts = []
    prior = case.get("preoffers", [])
    for index, kind in enumerate(prior):
        if index:
            receipts.append({
                "tool": "hub_read_devices",
                "arguments": {"deviceId": str(index), "attribute": "switch"},
                "success": True, "effect": "read",
            })
        assert budget.offer(kind, receipts)
    if case.get("newRead"):
        receipts.append({
            "tool": "hub_read_devices",
            "arguments": {"deviceId": "42", "attribute": "power"},
            "success": True, "effect": "read",
        })
    return budget, receipts


def _can_render(case, kind):
    if kind == "missing-required-source" and case.get("viewAvailable") is False:
        return None
    return case["prompts"].get(kind)


def _offer(case, kind, budget, receipts):
    # Original no-tool paths all require the already admitted tool view, but
    # missing source never exposes extra gateways.
    if kind != "missing-required-source" and case.get("toolAvailable") is False:
        return False
    return budget.offer(kind, receipts)


def _old_selection(case, budget, receipts):
    """Independent v0.18.354 post-grounding branch order, held constant."""
    for kind in LATE_SOURCE_ORDER:
        if kind not in case["admitted"]:
            continue
        prompt = _can_render(case, kind)
        if not isinstance(prompt, str) or not prompt.strip():
            continue
        if _offer(case, kind, budget, receipts):
            return kind
    return None


def _new_selection(case, budget, receipts):
    traces = []
    candidates = []
    # Reverse construction proves source precedence, not Python list order.
    for kind in reversed(LATE_SOURCE_ORDER):
        def admitted(k=kind):
            traces.append(("admitted", k))
            return k in case["admitted"]

        def render(k=kind):
            traces.append(("render", k))
            return _can_render(case, k)

        candidates.append(ModelSourceFollowup(
            kind=kind,
            admitted=admitted,
            render=render,
            read_gateways=() if kind == "missing-required-source" else READ_GATEWAYS,
            read_view_only=(kind == "missing-required-source"),
            metric="source-recovery",
        ))
    selected = choose_model_source_followup(
        candidates,
        order=LATE_SOURCE_ORDER,
        offer=lambda kind: _offer(case, kind, budget, receipts),
    )
    return selected, traces


def test_frozen_late_source_proposals_match_previous_priority():
    source = json.loads(FIXTURE.read_text())
    assert source["order"] == list(LATE_SOURCE_ORDER)
    assert len(source["cases"]) >= 12
    for case in source["cases"]:
        old_budget, old_receipts = _init(case)
        new_budget, new_receipts = _init(case)
        baseline = _old_selection(case, old_budget, old_receipts)
        selected, traces = _new_selection(case, new_budget, new_receipts)
        actual = selected[0].kind if selected else None
        assert baseline == case["expected"], case["id"]
        assert actual == baseline, case["id"]
        assert old_budget.offered_kinds == new_budget.offered_kinds, case["id"]
        assert old_receipts == new_receipts, case["id"]
        if selected:
            candidate, prompt = selected
            assert prompt == case["prompts"][actual], case["id"]
            assert candidate.metric == "source-recovery"
            later = set(LATE_SOURCE_ORDER[LATE_SOURCE_ORDER.index(actual) + 1:])
            assert not any(kind in later for _, kind in traces), case["id"]


def test_read_view_exception_is_only_for_unchecked_source():
    unsafe = ModelSourceFollowup(
        kind="diagnostic-discriminator", admitted=lambda: True,
        render=lambda: "bad", read_gateways=(), metric="x",
        read_view_only=True,
    )
    assert choose_model_source_followup(
        [unsafe], order=LATE_SOURCE_ORDER, offer=lambda _: True,
    ) is None

    unsafe_write = ModelSourceFollowup(
        kind="driver-or-controller", admitted=lambda: True,
        render=lambda: "bad", read_gateways=("hub_set_device",), metric="x",
    )
    assert choose_model_source_followup(
        [unsafe_write], order=LATE_SOURCE_ORDER, offer=lambda _: True,
    ) is None

    missing = ModelSourceFollowup(
        kind="missing-required-source", admitted=lambda: True,
        render=lambda: "read currently declared source",
        read_gateways=(), metric="x", read_view_only=True,
    )
    assert choose_model_source_followup(
        [missing], order=LATE_SOURCE_ORDER, offer=lambda _: True,
    )[0].kind == "missing-required-source"


def test_no_priority_override_or_new_permission_is_admitted():
    candidate = ModelSourceFollowup(
        kind="driver-or-controller", admitted=lambda: True,
        render=lambda: "read source", read_gateways=READ_GATEWAYS, metric="x",
    )
    assert choose_model_source_followup(
        [candidate], order=("driver-or-controller",), offer=lambda _: True,
    ) is None


def test_orchestrator_keeps_late_source_plan_after_grounding():
    source = (APP_DIR / "mcp_agent_orchestrator.py").read_text()
    assert "late_source = choose_model_source_followup(" in source
    assert "order=LATE_SOURCE_ORDER" in source
    assert source.count("late_source = choose_model_source_followup(") == 1
    assert source.index("decision = grounding.decide_no_tool_calls(") < source.index(
        "late_source = choose_model_source_followup("
    )
    assert source.index("late_source = choose_model_source_followup(") < source.index(
        "# A semantic investigation declares source *classes*"
    )
    assert "increment_active_metric(late_candidate.metric)" in source
