# Hubitat MCP AI 0.16.109

## Natural duration units and concise caveats

- Changes user-facing temporal summary prose from wire-style abbreviations such as `10m` to natural wording such as `10 minutes`.
- Changes interval-table duration cells from compact machine-style values such as `5m 36s` to readable `5 min 36 sec` while preserving exact interval seconds.
- Keeps internal structured/debug duration fields unchanged, including `totalActiveSeconds`, `totalActiveDuration`, and per-interval `durationSeconds`.
- Removes a redundant second unverified-event-stream estimate sentence when the deterministic duration guard has already rendered the full retained-history and source-integrity caveat.
- Preserves the 0.16.107 retained-page completeness rules and the 0.16.108 structured table presentation.
- Adds regression coverage for the exact duplicated caveat observed in the 0.16.108 Bathroom Light 1 live response.
