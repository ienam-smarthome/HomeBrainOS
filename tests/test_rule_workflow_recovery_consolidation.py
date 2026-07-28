from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import automation_rule_direct_contact as direct_contact
import automation_rule_workflow_recovery as recovery


REMOVED_MODULES = (
    "automation_rule_workflow_backup_confirmed",
    "automation_rule_workflow_backup_filename_safe",
    "automation_rule_workflow_write_safe",
    "automation_rule_workflow_split_repair",
)


def test_recovery_layers_have_one_externally_wired_owner() -> None:
    assert (APP / "automation_rule_workflow_recovery.py").is_file()
    for module_name in REMOVED_MODULES:
        assert not (APP / f"{module_name}.py").exists()


def test_recovery_safety_stage_order_is_preserved() -> None:
    assert recovery.ConfirmedBackupWashingRuleMachineWorkflow.__bases__ == (
        recovery.FinalWashingRuleMachineWorkflow,
    )
    assert recovery.FilenameSafeBackupWashingRuleMachineWorkflow.__bases__ == (
        recovery.ConfirmedBackupWashingRuleMachineWorkflow,
    )
    assert recovery.WriteSafeBackupWashingRuleMachineWorkflow.__bases__ == (
        recovery.FilenameSafeBackupWashingRuleMachineWorkflow,
    )
    assert recovery.SplitRepairWashingRuleMachineWorkflow.__bases__ == (
        recovery.WriteSafeBackupWashingRuleMachineWorkflow,
    )
    assert recovery.RepairIdSafeWashingRuleMachineWorkflow.__bases__ == (
        recovery.SplitRepairWashingRuleMachineWorkflow,
    )


def test_direct_contact_workflow_uses_consolidated_recovery_owner() -> None:
    assert (
        direct_contact.RepairIdSafeWashingRuleMachineWorkflow
        is recovery.RepairIdSafeWashingRuleMachineWorkflow
    )
    assert (
        direct_contact.install_repair_id_safe_rule_machine_workflow
        is recovery.install_repair_id_safe_rule_machine_workflow
    )


def test_consolidated_owner_preserves_all_installers() -> None:
    expected = {
        "install_confirmed_backup_rule_machine_workflow",
        "install_filename_safe_backup_rule_machine_workflow",
        "install_write_safe_backup_rule_machine_workflow",
        "install_split_repair_rule_machine_workflow",
        "install_repair_id_safe_rule_machine_workflow",
    }
    assert expected.issubset(set(recovery.__all__))
