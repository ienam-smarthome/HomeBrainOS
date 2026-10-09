# HomeBrainOS v0.16.147 — Historical scheduler-probe synthesis guard

## Live v0.16.146 finding
v0.16.146 correctly moved adaptive diagnostic log reads before the current request's targeted scheduler probes. The live evidence proves the ordering: the MCP Rule Server scoped log read completed before the six targeted `hub_get_device` calls, and the inventory report recorded `ranAfterDiagnosticLogReads=true`.

However, the 6-hour scoped log window still contained `Device not found` rows created by the **previous v0.16.145 HomeBrain diagnostic request**. Synthesis therefore repeated the unsupported diagnosis "MCP Rule Server Orphaned Device Requests" and recommended removing references, even while the deterministic inventory section correctly warned that scheduler probes can create those rows.

## Fix
- Add a deterministic finalization guard keyed to the scheduler secondary-source provenance metadata.
- When Rule Server not-found/cleanup claims overlap IDs recorded in `probedExamples`, preserve the unresolved lookup observation but block inference of:
  - deleted/non-existent devices,
  - persisted Rule Server configuration references,
  - orphaned scheduler ownership,
  - safe removal or cleanup.
- Historical matching log rows are explicitly described as potentially originating from an earlier HomeBrain scheduler diagnostic request.
- Unrelated Rule Server errors remain untouched.
- Add regression tests for the exact v0.16.146 live wording and fail-closed conditions.

## Safety
No Hubitat devices, apps, rules, jobs, schedules or settings are changed. The fix affects final evidence interpretation only.
