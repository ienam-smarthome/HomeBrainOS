# Hubitat MCP AI 0.16.118

## Changed

- Investigate offline devices by the exact IDs supplied in the System Check device-health section; no longer require an ID to be embedded in the prose alert title. Offline findings now retain the identity of the health attribute, reported battery level (if supplied) and last known activity (if available), and print this source evidence in the comprehensive chat audit.
- Deduplicate up to four read-only, six-hour scoped log follow-ups. Prioritise unavailable device identities and observed app failures; include performance outliers only within the remaining budget.
- Revisit recent SenseCap D1 live-push errors found in the previous audit snapshot. When SenseCap is among sampled performance apps, perform a bounded follow-up for explicit live-push recovery logs without assuming continuous operation. Never claim an HTTP 408 failure is repaired solely because it is absent from the latest capped error sample.
- Distinguish historical MCP log transport success from evidence that returned timestamps support the requested date window. Mark empty, undated and out-of-window responses as unable to support historical-coverage claims.
- Preserve per-tool receipts and Hubitat write-confirmation boundaries. Requests to perform comprehensive audits remain read-only, without unattended repair or unsupported model synthesis.

## Validation

- Added regression tests for identity-based offline log reads and states, source-field availability, previous SenseCap failures, timestamp-grounded recovery signals and write-free execution.
- Full release gate, Python suite and add-on container smoke test must be confirmed in CI before merging.
