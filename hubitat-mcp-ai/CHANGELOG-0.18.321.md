# HomeBrainOS v0.18.321 — Stage 8.6 bounded command-event source coverage diagnostics

## Why this stage
The first real Command Shadow test (device 7103, UTC 2026-10-12) successfully completed each of three read-only Hubitat gateway calls (`command-off`, `command-on`, `switch`) but returned **zero day-matching events**. The Historical Journal independently retains six reported switch rows for the incident period. These sources are not equivalent: a current bounded upstream history page may be empty, have a later date range, be cut off by a 50-row cap, or return a successful but unrecognised payload. None of those conditions proves the 12 October incident was event-free.

## Changes
- Audit **the same three source responses** without any additional MCP reads or retries.
- Distinguish an actual empty `events: []` page from transport success with a missing/malformed events array. The latter is a **partial/unusable source**, not successful empty history.
- Show fixed-count per-page details: source row count (up to 50), valid UTC dates, matching-day rows, before/after target-day rows, unexpected operations, mismatched numeric device IDs, rejected timestamps/values, and whether the page reached the 50-row cap.
- For eligible single-device rows, report the first/last *visible* event timestamp to reveal gaps between source-page coverage and the selected UTC day. This is not a true device-history coverage window; unreturned pages/older events remain unknown.
- Classify zero-match outcomes as `bounded_sources_no_day_matches` with plain-language caveats. Distinguish `partial_or_failed_read` for malformed responses or actual read errors.
- No raw event descriptions, producer names, log messages, private identifiers, addresses, or unrelated device timestamps are released in diagnostic output. No new app logs or journal captures.
- Preserve false history completeness, independent source clock authentication, device delivery, physical actuation, causal attribution and publisher approval. All diagnostic results are deterministic and postrun.
- New synthetic tests cover true empty pages, unrecognised successful payloads, later-only records, excluded records, page caps, failed operations and redaction.

## Acceptance
Upgrade to v0.18.321, run **Live Shadow → Command Shadow** again for device ID `7103`, UTC date `2026-10-12`, with fresh consent. Inspect **Source page coverage diagnostics**. If all three report zero source rows, the endpoint exposes no evidence through those filters; do not spend more requests repeating them. If rows exist but dates are later, lookback/pagination/retention is a likely limitation (not independently proven). If events are filtered out, the counters identify the stage of exclusion.

No model-led live publication, Hubitat device commands, or Cloud requests were added. CI is mocked and cannot establish actual upstream history availability.