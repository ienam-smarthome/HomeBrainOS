# Hubitat MCP AI 0.16.119

## Changes

- Report scoped warning/error patterns separately from main health alerts, with source IDs, repeated log row counts and timestamps where available. Do not interpret multiple log rows as distinct outages.
- Correct offline-device provenance in the active semantic health audit. Retain the health source field, battery and last activity when Hubitat provides them.
- Correlate SenseCap D1 live-push failures, configuration-push failures and explicit recovery messages without declaring a cause or confirmed recovery from incomplete evidence.
- Include latency of scoped log reads in evidence receipts.
- Skip the optional older-log request after three or more scoped diagnostic requests to limit hub load; clearly disclose that historical coverage is not verified.
- Preserve read-only diagnostics and existing confirmation requirements for device or app modifications.

## Validation

- Regression tests added for the active offline-device code, scoped findings, SenseCap log categorisation and bounded log requests.
- Verify full Python suite and release checks before merging.
