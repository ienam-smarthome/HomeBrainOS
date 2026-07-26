# Hubitat MCP AI 0.10.155

## Changed

- Consolidated authoritative notification-device discovery, guarded
  washing-machine Rule Machine compilation and verified recent-backup preflight
  in `automation_rule_workflow_washing.py`.
- Preserved the exact `NativeRuleMachineAutomationWorkflow` →
  `NotificationSafeNativeRuleMachineWorkflow` →
  `WashingRuleMachineWorkflow` → `FinalWashingRuleMachineWorkflow` class order.
- Preserved all public workflow classes, helpers and installer entry points.
- Redirected the downstream backup workflow and focused test consumers to the
  consolidated washing owner.

## Removed

- Removed two superseded sibling-only modules:
  `automation_rule_workflow_notification_safe.py` and
  `automation_rule_workflow_washing_final.py`.

## Validation

- AST equivalence checks for all 13 moved notification and final-washing
  definitions.
- Notification, washing, backup, write and repair baseline suites.
- Import and cluster analysis.
- Repository layout validation.
- Python compilation.
- Blocking release gate.
