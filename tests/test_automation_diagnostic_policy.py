from __future__ import annotations

from automation_diagnostic_policy import (
    AUTOMATION_DIAGNOSTIC_INSTRUCTION,
    is_automation_runtime_diagnostic,
    is_broad_automation_runtime_diagnostic,
)
from automation_status_service import AutomationStatusService


def test_short_marker_inventory_does_not_enter_reasoning_loop():
    for question in ("show broken automations", "list disabled rules", "which apps are active"):
        assert not is_automation_runtime_diagnostic(question)
        assert AutomationStatusService.matches_request(question)


def test_failure_and_root_cause_questions_are_not_inventory_requests():
    questions = (
        "show which automations are failing",
        "why is my fridge door automation not working?",
        "diagnose rule 2957 broken action and missing device targets",
        "which rules have execution errors?",
        "inspect all my automations for invalid actions",
    )
    for question in questions:
        assert is_automation_runtime_diagnostic(question)
        assert not AutomationStatusService.matches_request(question)
    assert "compiled action" in AUTOMATION_DIAGNOSTIC_INSTRUCTION
    assert "Never silently repair" in AUTOMATION_DIAGNOSTIC_INSTRUCTION


def test_broad_diagnostic_goes_to_read_only_audit_and_targeted_uses_model():
    assert is_broad_automation_runtime_diagnostic("which automations are failing?")
    assert is_broad_automation_runtime_diagnostic("inspect all my automations for errors")
    assert not is_broad_automation_runtime_diagnostic("why is rule 2957 not working?")
    assert not is_broad_automation_runtime_diagnostic("why did hub rule 2957 fail?")
    assert not is_broad_automation_runtime_diagnostic("show broken automations")
    assert not is_broad_automation_runtime_diagnostic("fix all my failing automations")


def test_sources_without_active_signal_are_not_misrepresented_as_explicit_evidence():
    from mcp_client import MCPToolResult
    result = MCPToolResult(
        name="hub_read_apps_code", arguments={}, raw={}, text="ok",
        data={"apps": [{"id": 3995, "label": "Humidity Controller", "disabled": False}]},
    )
    items = AutomationStatusService._items_from_result(result, item_type="app", source="hub_read_apps_code")
    assert len(items) == 1
    entry = items[0]
    assert entry["status"] == "active"
    assert entry["active"] is True
    assert entry["explicit_active_signal"] is False
    assert entry["runtime_verified"] is False
    assert entry["status_basis"] == "inferred_from_non_disabled_configuration"


def test_disabled_and_broken_items_do_not_claim_active_status():
    from mcp_client import MCPToolResult
    result = MCPToolResult(
        name="hub_read_apps_code", arguments={}, raw={}, text="ok",
        data={"apps": [
            {"id": 5, "label": "Disabled rule", "disabled": True},
            {"id": 6, "label": "Broken rule *BROKEN*", "active": True},
        ]},
    )
    items = AutomationStatusService._items_from_result(result, item_type="app", source="hub_read_apps_code")
    assert [row["active"] for row in items] == [False, False]
    assert items[1]["explicit_active_signal"] is True
