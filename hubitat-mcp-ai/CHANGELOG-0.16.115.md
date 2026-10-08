# Hubitat MCP AI 0.16.115

## Changed

- Separates `*BROKEN*` name markers from independently supported faults in comprehensive chat-audit reporting. Existing automation status data remain unmodified; seven name-marked rules no longer appear as confirmed failures solely due to the label.
- Preserves exact MCP-visible device IDs in the internal System Check snapshot and reports the overlap with top-ranked performance-device IDs. Distinct source populations are explicitly labelled, without assuming that differing counts indicate missing devices.
- Identifies saturation of the 200-row, 24-hour log request and cautions that older errors might not be represented.
- Extracts human-readable MCP Rule Server entry messages from structured JSON envelopes in scoped logs.
- Returns individual, correctly success-labelled receipts for the audit's device, automation and log sections plus performance reads and scoped log follow-ups.
- Correlates directly observed symptoms to safe, device-specific inspection steps, without triggering writes or inferring causality from performance share.
- Explicitly discloses that the chat report is host-assembled and does not execute an LLM reasoning round. Deeper model synthesis and controlled repair execution remain separate future features.

## Validation

- Adds regression coverage for source-population comparisons, `*BROKEN*` name markers, saturated log windows, structured error extraction, source receipts and partial audit failures.
- Full release gate and container smoke test results to be verified in GitHub Actions before merge.
