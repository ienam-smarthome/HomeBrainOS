from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import automation_rule_workflow_recovery as repair
import automation_rule_workflow_recovery as washing
from automation_rule_workflow_hubitat import NativeRuleMachineAutomationWorkflow


REMOVED_MODULES = (
    "automation_rule_workflow_notification_safe",
    "automation_rule_workflow_washing",
    "automation_rule_workflow_washing_final",
)


def test_notification_and_final_washing_layers_have_one_owner() -> None:
    assert (APP / "automation_rule_workflow_recovery.py").is_file()
    for module_name in REMOVED_MODULES:
        assert not (APP / f"{module_name}.py").exists()


def test_washing_safety_stage_order_is_preserved() -> None:
    assert washing.NotificationSafeNativeRuleMachineWorkflow.__bases__ == (
        NativeRuleMachineAutomationWorkflow,
    )
    assert washing.WashingRuleMachineWorkflow.__bases__ == (
        washing.NotificationSafeNativeRuleMachineWorkflow,
    )
    assert washing.FinalWashingRuleMachineWorkflow.__bases__ == (
        washing.WashingRuleMachineWorkflow,
    )


def test_backup_chain_uses_the_consolidated_final_washing_class() -> None:
    assert repair.ConfirmedBackupWashingRuleMachineWorkflow.__bases__ == (
        washing.FinalWashingRuleMachineWorkflow,
    )
