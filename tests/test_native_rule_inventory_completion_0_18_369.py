"""Typed native inventory completion must never inherit action-tree audit duties.

Synthetic facts only: the user's real v0.18.368 inventory showed native
candidate ID 169 with no matched type and zero suffix matches, but the model-
independent answer was incorrectly scored under existing_rule_verification.
"""
from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from mcp_agent_orchestrator import AgentOutcome  # noqa: E402
from observed_agent_outcome import build_observed_agent_outcome  # noqa: E402
from shared_investigation_completion import apply_shared_investigation_completion  # noqa: E402
from native_rule_inventory_source import (  # noqa: E402
    project_rule_inventory, render_inventory,
)

QUESTION = (
    'Read-only native Rule Machine investigation. Use hub_list_apps(scope="instances") '
    'and hub_list_rules to identify the installed Rule Machine parent and '
    'find existing rules whose names end with (One-time YYYY-MM-DD HH:MM). '
    'Do not create or update anything.'
)

TYPES = {
    "apps": [{"id": 18, "name": "Rule Machine", "namespace": "hubitat",
              "system": True, "isBuiltIn": True}],
    "count": 1,
}
INST = {"apps": [
    {"id": 169, "name": "Rule Machine", "type": "Rule Machine",
     "appTypeId": None, "parentId": None},
], "count": 1, "totalOnHub": 1, "filter": "all"}
RULES = {"rules": [], "count": 0}


def _response(instances=INST, types=TYPES, rules=RULES):
    projection = project_rule_inventory(instances, types, rules)
    packet = [{
        "tool": "homebrain_native_rule_inventory",
        "evidence_kind": "typed_native_rule_inventory",
        "success": True, "mutates": False, "effect": "read",
        "details": deepcopy(projection),
    }]
    original = AgentOutcome(
        message=render_inventory(projection), request_class="live-read",
        evidence=packet, choices=[],
        investigation_coverage=None,
    )
    observed = build_observed_agent_outcome(original, {
        "outcome": "success", "counters": {}, "timings_ms": {},
    })
    return apply_shared_investigation_completion(observed, QUESTION)


def test_0_18_368_live_shape_is_unresolved_for_specific_parent_join_only():
    assessed = _response()
    c = assessed.investigation_coverage
    assert c["domain"] == "native_rule_inventory"
    assert c["questionResolved"] is False
    assert c["oneTimeMatchCount"] == 0
    assert c["absenceScope"] == "complete-exact-suffix-current-inventory"
    assert assessed.metrics["outcome"] == "unresolved"
    assert [r["key"] for r in c["requirements"]] == [
        "native_parent_identity", "one_time_rule_inventory",
        "native_document_if_matching",
    ]
    assert "stored_logic" not in str(c)
    assert "comparison controller" not in assessed.message
    assert "No exact one-time suffix matched" in assessed.message
    assert "169" in assessed.message
    assert "instance-appTypeId-absent" in str(project_rule_inventory(INST, TYPES, RULES))
    assert "did not provide an appTypeId" in assessed.message


def test_exact_type_id_join_and_complete_list_resolve_inventory():
    inst = deepcopy(INST)
    inst["apps"][0]["appTypeId"] = 18
    assessed = _response(instances=inst)
    c = assessed.investigation_coverage
    assert c["domain"] == "native_rule_inventory"
    assert c["questionResolved"] is True
    assert c["evidenceComplete"] is True
    assert c["status"] == "inventory-complete"
    assert assessed.metrics["outcome"] == "success"
    assert "ID **169**" in assessed.message


def test_incomplete_name_list_never_claims_absence():
    rules = {"rules": [], "count": 0, "nextCursor": "3"}
    inst = deepcopy(INST)
    inst["apps"][0]["appTypeId"] = 18
    assessed = _response(instances=inst, rules=rules)
    assert assessed.investigation_coverage["questionResolved"] is False
    assert assessed.investigation_coverage["absenceScope"] == "incomplete-inventory"
    assert assessed.metrics["outcome"] == "unresolved"
    assert "incomplete reads do not establish absence" in assessed.message


def test_unlinked_but_named_rule_machine_is_not_promoted_to_native_parent():
    types = deepcopy(TYPES)
    types["apps"][0]["namespace"] = "user"
    assessed = _response(types=types)
    assert assessed.investigation_coverage["questionResolved"] is False
    assert "ID **169**" not in assessed.message
    assert assessed.investigation_coverage["recordedCandidateParentIds"] == ["169"]


def test_forged_or_mutating_typed_projection_does_not_gain_inventory_coverage():
    projection = project_rule_inventory(INST, TYPES, RULES)
    original = AgentOutcome(
        message="App 169 is a native parent", request_class="live-read",
        evidence=[{"tool": "homebrain_native_rule_inventory",
                   "evidence_kind": "typed_native_rule_inventory",
                   "success": True, "mutates": True, "effect": "sensitive_write",
                   "details": projection}],
        choices=[], investigation_coverage=None,
    )
    observed = build_observed_agent_outcome(
        original, {"outcome": "success", "counters": {}, "timings_ms": {}}
    )
    assessed = apply_shared_investigation_completion(observed, QUESTION)
    assert getattr(assessed, "investigation_coverage", None) is None or (
        assessed.investigation_coverage.get("domain") != "native_rule_inventory"
    )


def test_native_parent_diagnostic_never_exposes_unrelated_app_types():
    types = deepcopy(TYPES)
    types["apps"].append({
        "id": 19, "name": "Unrelated private app", "namespace": "person",
        "userName": "private-name",
    })
    types["count"] += 1
    projection = project_rule_inventory(INST, types, RULES)
    assert projection["nativeRuleMachineTypeIds"] == ["18"]
    assert "Unrelated private app" not in str(projection)
    assert "private-name" not in str(projection)
