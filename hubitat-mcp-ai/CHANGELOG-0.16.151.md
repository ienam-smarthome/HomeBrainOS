# Hubitat MCP AI 0.16.151

## Scheduler probe-history cleanup guard

Live verification of 0.16.150 showed that the scheduler-probe provenance warning was present, but the synthesized report could still emit a contradictory cleanup action such as **"Remove orphaned device references"** when the MCP Rule Server section heading used the word "Cleanup" and the action line itself omitted the probed IDs.

This release tightens the deterministic final evidence guard:

- MCP Rule Server cleanup sections are treated as probe-history-sensitive when the current scheduler cross-check records that targeted `hub_get_device` probes may emit expected `Device not found` rows.
- Recommendation-table rows containing `Device not found` are qualified even when they do not use the words "missing device".
- Generic **Orphaned References** labels and cleanup actions are replaced with the existing unresolved/provenance warning rather than being allowed to imply deletion or persisted Rule Server configuration.
- Regression coverage reproduces the exact 0.16.150 report shape: the System Errors table row, Orphaned References qualifier, Cleanup heading, and ID-free remove-reference action.

No Hubitat device, app, rule, schedule, or setting is changed. Failed targeted reads remain unresolved observations and are not evidence of deletion, ownership, or safe cleanup.
