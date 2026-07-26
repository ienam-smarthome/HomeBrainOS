# Hubitat MCP AI 0.10.154

## Changed

- Consolidated live MCP tool-schema handling, release-specific notification and
  operation safeguards, and native Rule Machine execution in
  `automation_rule_workflow_native_rm.py`.
- Preserved the exact `AutomationRuleWorkflow` →
  `LiveSchemaAutomationRuleWorkflow` → `ReleaseAutomationRuleWorkflow` →
  `NativeRuleMachineAutomationWorkflow` class order.
- Preserved the release layer's strict notification-device replacement through
  an explicit consolidated module alias.
- Redirected downstream workflow and focused test consumers to the native owner.

## Removed

- Removed two superseded sibling-only modules:
  `automation_rule_workflow_live.py` and
  `automation_rule_workflow_release.py`.

## Validation

- AST equivalence checks for all 14 schema, release and native definitions.
- Live schema, release, native and downstream safety baseline suites.
- Import and cluster analysis.
- Repository layout validation.
- Python compilation.
- Blocking release gate.
