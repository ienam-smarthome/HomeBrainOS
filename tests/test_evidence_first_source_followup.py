"""Frozen anonymous source-choice replay, not a model-accuracy benchmark."""
from __future__ import annotations
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
from evidence_first_checkpoint_plan import SourceCheckpointBudget
from evidence_first_source_followup import (
    EARLY_SOURCE_ORDER, ModelSourceFollowup, choose_model_source_followup,
)

FIXTURE = Path(__file__).parent / "fixtures" / "q3_early_source_replay_v1.json"
GATEWAYS = ("hub_read_devices",)


def initialize(case):
    budget = SourceCheckpointBudget(max_offers=3)
    receipts = []
    prior = case.get("preoffers", [])
    for index, kind in enumerate(prior):
        if len(prior) > 1:
            receipts.append({
                "tool": "hub_read_devices", "arguments": {"deviceId": str(index)},
                "success": True, "effect": "read",
            })
        assert budget.offer(kind, receipts)
    receipts.extend(case.get("successful_scopes", []))
    return budget, receipts


def legacy_select(case, budget, receipts):
    """Frozen v0.18.353 branch order: historical > input > inventory."""
    for kind in EARLY_SOURCE_ORDER:
        if kind not in case["admitted"]:
            continue
        text = case["candidate_prompts"].get(kind)
        if not isinstance(text, str) or not text.strip():
            continue
        if budget.offer(kind, receipts):
            return kind
    return None


def unified_select(case, budget, receipts):
    callbacks = []
    candidates = []
    for kind in reversed(EARLY_SOURCE_ORDER):
        def admitted(k=kind):
            callbacks.append(("admitted", k))
            return k in case["admitted"]

        def render(k=kind):
            callbacks.append(("render", k))
            return case["candidate_prompts"].get(k)

        candidates.append(ModelSourceFollowup(
            kind=kind, admitted=admitted, render=render,
            read_gateways=GATEWAYS, metric="source_followup",
            hide_inventory=kind == "inventory-evidence",
        ))
    selected = choose_model_source_followup(
        candidates, offer=lambda kind: budget.offer(kind, receipts),
    )
    return (selected[0].kind if selected else None), callbacks, selected


def test_frozen_synthetic_replay_preserves_source_choices():
    cases = json.loads(FIXTURE.read_text())["cases"]
    assert len(cases) >= 8
    for case in cases:
        legacy_budget, old_receipts = initialize(case)
        new_budget, new_receipts = initialize(case)
        expected_old = legacy_select(case, legacy_budget, old_receipts)
        result, callbacks, selected = unified_select(case, new_budget, new_receipts)
        assert expected_old == case["expected"], case["id"]
        assert result == expected_old, case["id"]
        assert old_receipts == new_receipts
        assert legacy_budget.offered_kinds == new_budget.offered_kinds
        if selected:
            assert selected[1] == case["candidate_prompts"][result]
            assert selected[0].read_gateways == GATEWAYS
        # No lower-priority generator is evaluated after acceptance.
        if result:
            selected_index = EARLY_SOURCE_ORDER.index(result)
            lower = set(EARLY_SOURCE_ORDER[selected_index + 1:])
            assert not any(k in lower for _, k in callbacks), case["id"]


def test_source_plan_does_not_infer_missing_read_permissions():
    candidate = ModelSourceFollowup(
        kind="target-history", admitted=lambda: True,
        render=lambda: "Source is required", read_gateways=(),
        metric="source",)
    assert choose_model_source_followup(
        [candidate], offer=lambda _: True) is None


def test_source_plan_skips_invalid_and_unverified_proposal():
    valid = ModelSourceFollowup(
        kind="upstream-input", admitted=lambda: True,
        render=lambda: "Read input", read_gateways=GATEWAYS,
        metric="source",)
    bad = ModelSourceFollowup(
        kind="unknown", admitted=lambda: True,
        render=lambda: "Mutation?", read_gateways=("hub_set_device",),
        metric="write",)
    chosen = choose_model_source_followup(
        [bad, valid], offer=lambda _: True)
    assert chosen[0].kind == "upstream-input"


def test_source_plan_is_pure_and_does_not_execute_callbacks_for_rejected():
    calls = []
    rejected = ModelSourceFollowup(
        kind="target-history", admitted=lambda: False,
        render=lambda: calls.append("bad") or "bad",
        read_gateways=GATEWAYS, metric="source",)
    chosen = choose_model_source_followup(
        [rejected], offer=lambda _: calls.append("offer") or True)
    assert chosen is None
    assert not calls


def test_orchestrator_uses_one_early_source_plan_not_three_independent_branches():
    source = (APP / "mcp_agent_orchestrator.py").read_text()
    # The new call site chooses one proposed obligation and applies gateway
    # and metric metadata once; deeper mandatory source reads remain separate.
    assert "early_source = choose_model_source_followup(" in source
    assert "increment_active_metric(source_candidate.metric)" in source
    assert source.count("early_source = choose_model_source_followup(") == 1
