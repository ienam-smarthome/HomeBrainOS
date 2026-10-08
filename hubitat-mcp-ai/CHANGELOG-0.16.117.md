# Hubitat MCP AI 0.16.117

## Changed

- Prioritise read-only scoped log follow-ups for explicit observed hub-audit faults before the strongest sampled performance outliers (up to four unique targets). SenseCap D1 HTTP 408 live-push failures now receive an app-specific follow-up even when performance statistics are unavailable.
- Do not equate successfully returned empty historical logs with validated time-filter support or historical log retention. Inspect actual returned row timestamps against the requested start/end boundaries; disclose zero/undated/out-of-window results as unverified and show observed timestamp ranges only when present.
- Explain SenseCap D1's distinct live-push suspension and automatic backoff status without claiming recovery before evidence.
- Surface observed `hub_list_devices` format/`attributeNames` validation failures, explicitly noting that the current MCP log does not identify which upstream caller sent the malformed request.
- Include performance-sampled device IDs next to their names when they are absent from the current inventory; do not infer whether these are deleted, hidden or historical from a name alone.
- Preserve original source-evidence receipts and write-confirmation safeguards; the comprehensive chat route remains read-only and host-assembled.

## Validation

- Added regression coverage for fault-first selection, deduplication, unavailable performance reads, real-world MCP validation wording, historical window verification and explicit unmatched IDs.
- CI release gate, Python tests and add-on smoke test to be verified before merge.
