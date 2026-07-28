from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from automation_rule_workflow import AutomationRuleWorkflow
import automation_rule_workflow_hubitat as native


REMOVED_MODULES = (
    "automation_rule_workflow_live",
    "automation_rule_workflow_release",
)


def test_rule_schema_and_release_have_one_native_owner() -> None:
    assert (APP / "automation_rule_workflow_hubitat.py").is_file()
    for module_name in REMOVED_MODULES:
        assert not (APP / f"{module_name}.py").exists()


def test_native_workflow_stage_order_is_preserved() -> None:
    assert native.LiveSchemaAutomationRuleWorkflow.__bases__ == (
        AutomationRuleWorkflow,
    )
    assert native.ReleaseAutomationRuleWorkflow.__bases__ == (
        native.LiveSchemaAutomationRuleWorkflow,
    )
    assert native.NativeRuleMachineAutomationWorkflow.__bases__ == (
        native.ReleaseAutomationRuleWorkflow,
    )


def test_release_notification_patch_targets_native_owner() -> None:
    assert native.live_module is native
    assert native._is_notification_device is native._strict_notification_device
