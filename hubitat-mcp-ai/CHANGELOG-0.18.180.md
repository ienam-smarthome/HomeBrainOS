# HomeBrainOS v0.18.180 — model-selected read-only whole-hub diagnostics

## What prompted this release

The natural-language request "check hub logs for any issues" caused Investigation
V2 to return HTTP 422 because its single-device investigation executor attempted
to resolve the whole-hub log audit as a device name. A successful reference
investigation inspected multiple apps and hub alerts without requiring a device
ID. This is a scope/capability mismatch, not missing user information.

## Changes

- The semantic model can now choose a `diagnostics` objective with
  `scope=all`. A general `investigation` objective with `scope=all` also
  maps to the whole-hub diagnostic capability. The host strictly validates the
  plan; model-provided tools, IDs, arguments and writes remain unauthorised.
- The V2 test path invokes the established deterministic System Check service
  with `persist=False`, so it does **not** update existing morning-report
  snapshots, schedules, Hubitat devices or automations.
- The new report preserves bounded source coverage, warnings/errors,
  device and automation findings and explicit log-source failure indicators.
  A successful MCP request does not prove exhaustive log coverage.
- The browser shows system-audit metrics without inventing a device target.
  Source text is bounded and redactable, and is displayed using textContent.
- When V2 has an already source-backed latest-switch incident but its MCP read
  budget is exhausted, it now skips BOTH the futile planner and the redundant
  atomic/narrative model synthesis calls; the host cites the attested evidence
  directly with historical/physical limits. This addresses a second cause of
  the observed 171.853-second v0.18.179 run; actual P95 still needs live tests.
- Regression tests cover the original whole-hub 422 scenario, safe scope
  validation, system-wide fallback, log-read failures, redaction and a strict
  non-persistence audit call.

## What this does not yet achieve

- Not a general-purpose native MCP tool-calling loop.
- A model can still misclassify the objective; failed or unsupported
  classification must not be promoted to verified device authority.
- Log history is a bounded sample. Existing app-specific log API failures,
  cold device inventory latency, and v0.18.179 long wall-clock results remain
  separate work items.
- No live Hubitat test or actual logging inventory is implied by these
  offline tests. An operator must enable V2 testing and submit a new request.

## Live acceptance after release

Ask V2: "check hub logs for any issues".

Expected: `semantic_system_diagnostics`, no device resolution attempted,
source-backed warnings/errors and explicit log coverage. Do not claim the hub
has no errors when the log gateway fails. No device writes.
