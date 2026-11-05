"""Native Rule Machine parent identity checks remain after retiring list fast path.

Pure non-rendering source validation: no MCP calls, native write permission,
rendered editor page or rule creation. Protect writer preflight invariants.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from native_rule_parent_identity import _native_parent_from_summary

ROOT_ID = "169"
CLASS_ID = "18"


def _summary(**updates):
    return {
        "success": True, "id": 169, "name": "Rule Machine",
        "type": "Rule Machine", "namespace": "hubitat",
        "user": False, "appTypeId": 18, "parentId": None,
        **updates,
    }


def test_exact_native_parent_summary_from_nonrendering_source():
    parent, gap = _native_parent_from_summary(
        _summary(), candidate_id=ROOT_ID, candidate_type_id=CLASS_ID,
    )
    assert gap == ""
    assert parent == {
        "appId": ROOT_ID, "appTypeId": CLASS_ID,
        "namespace": "hubitat", "name": "Rule Machine",
        "proof": "source-typed-installed-app-summary",
    }


def test_nested_native_app_type_requires_consistent_identity():
    record = _summary()
    record["appType"] = {
        "id": 18, "namespace": "hubitat",
        "name": "Rule Machine", "system": True, "isBuiltIn": True,
    }
    parent, gap = _native_parent_from_summary(
        record, candidate_id=ROOT_ID, candidate_type_id=CLASS_ID,
    )
    assert parent and gap == ""


@pytest.mark.parametrize("summary,expected", [
    ({"success": False}, "native-app-summary-unavailable"),
    (_summary(id=42), "native-app-summary-id-mismatch"),
    (_summary(user=True), "native-app-summary-built-in-unverified"),
    (_summary(parentId=999), "native-app-summary-parent-conflict"),
    (_summary(type="Other"), "native-app-summary-type-conflict"),
    (_summary(appTypeId=999), "native-app-summary-class-id-conflict"),
    (_summary(namespace=None), "native-app-summary-class-namespace-unavailable"),
    (_summary(namespace="user"), "native-app-summary-class-namespace-unverified"),
    (_summary(appType={"id": 20, "namespace": "hubitat", "name": "Rule Machine"}),
     "native-app-summary-class-id-conflict"),
    (_summary(appType={"id": 18, "namespace": "user", "name": "Rule Machine"}),
     "native-app-summary-class-namespace-unverified"),
    (_summary(appType={"id": 18, "namespace": "hubitat", "name": "Rule Machine",
                       "isBuiltIn": False}),
     "native-app-summary-system-conflict"),
])
def test_missing_or_conflicting_source_never_certifies_parent(summary, expected):
    parent, gap = _native_parent_from_summary(
        summary, candidate_id=ROOT_ID, candidate_type_id=CLASS_ID,
    )
    assert parent is None
    assert gap == expected


def test_unrelated_user_record_is_not_exposed_in_parent_result():
    candidate = _summary()
    candidate["privateToken"] = "do-not-publish"
    parent, gap = _native_parent_from_summary(
        candidate, candidate_id=ROOT_ID, candidate_type_id=CLASS_ID,
    )
    assert gap == ""
    assert "do-not-publish" not in str(parent)
