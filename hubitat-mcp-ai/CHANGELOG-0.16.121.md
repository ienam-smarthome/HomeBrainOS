# Hubitat MCP AI 0.16.121

## Changes

- Add temporary opt-in `sensecap_d1_intentionally_powered_off` configuration (default false). When enabled, the read-only comprehensive chat audit labels SenseCap D1's known lack of power as user-supplied evidence, explains the expected live/config push failures, and avoids repeated scoped SenseCap log requests while retaining the original warning rows. Clear the setting when the device is powered on. Never assume a permanent power-off state.
- Consolidate slow internal `GET /logs/json` warnings with differing millisecond values into one fingerprint. Preserve occurrence counts and observed minimum/maximum request durations.
- Instrument MCP health, tool discovery, device inventory/classification, automation inventory, initial log read, and finding aggregation wall-clock times in the saved System Check and comprehensive audit report. This helps locate the actual slow audit stage before prescribing optimisations; these are not hub CPU percentages.
- Add opt-in `comprehensive_audit_ai_analysis_enabled` (default false). The existing configured model may provide up to three short evidence-grounded hypotheses in a tool-free request limited to 12 seconds. Suggestions are distinctly labelled non-authoritative and cannot execute hub operations. Timeout or provider failures leave the deterministic report intact.
- Preserve exact source provenance and the existing default read-only audit route and write confirmation safeguards.

## Validation

- Added regression tests for grouped slow-log durations, temporary power-off context, audit-stage timing and optional AI non-mutating behaviour and fallback.
- Require full Python tests, add-on container smoke test and release-assurance workflows green before merge.
