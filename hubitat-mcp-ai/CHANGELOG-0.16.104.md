# Hubitat MCP AI 0.16.104

## Small-limit temporal history analysis

- Fixes deterministic device-history duration analysis when a caller requests a small presentation limit such as `limit: 1`.
- Keeps `limit` as a user-facing cap on returned event rows while temporal interval arithmetic uses every matching state row from the authoritative fetched page.
- Prevents cases where `analysisEventCount` reports multiple switch events but `intervalCount` and duration incorrectly collapse to zero because only the newest displayed row was analysed.
- Preserves existing bounded-history and source-integrity semantics; the change does not promote an incomplete event stream to verified completeness.
- Adds regression coverage proving that a one-row presentation can still derive multiple bounded ON intervals from the full fetched history page.
