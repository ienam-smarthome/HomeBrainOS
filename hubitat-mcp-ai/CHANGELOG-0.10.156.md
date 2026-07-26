# Hubitat MCP AI 0.10.156

## Changed

- Consolidated notification discovery, guarded washing compilation, recent
  backup preflight, confirmed backup creation, filename/date validation, native
  write-route recovery, split rule population/repair and authoritative repair-ID
  verification in `automation_rule_workflow_repair_id_safe.py`.
- Preserved the exact `FinalWashingRuleMachineWorkflow` →
  `ConfirmedBackupWashingRuleMachineWorkflow` →
  `FilenameSafeBackupWashingRuleMachineWorkflow` →
  `WriteSafeBackupWashingRuleMachineWorkflow` →
  `SplitRepairWashingRuleMachineWorkflow` →
  `RepairIdSafeWashingRuleMachineWorkflow` class order.
- Preserved every public helper and installer entry point.
- Redirected focused tests to the externally wired recovery owner.

## Removed

- Removed five superseded sibling-only modules:
  `automation_rule_workflow_washing.py`,
  `automation_rule_workflow_backup_confirmed.py`,
  `automation_rule_workflow_backup_filename_safe.py`,
  `automation_rule_workflow_write_safe.py` and
  `automation_rule_workflow_split_repair.py`.

## Validation

- AST equivalence checks for all 40 washing and recovery definitions.
- Notification, washing, backup, write-recovery, split-repair, repair-ID and
  downstream direct-contact baseline suites.
- Import and cluster analysis.
- Repository layout validation.
- Python compilation.
- Blocking release gate.
