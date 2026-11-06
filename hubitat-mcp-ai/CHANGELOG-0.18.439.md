# HomeBrainOS v0.18.439 — verified empty native past-log response semantics

## Triggering real read-only evidence (6 November 2026)

The user-submitted v0.18.438 ordinary Ask technical JSON for the 5 November 16:52 Hubitat restart showed a successful `hub_get_logs(mode="past", since=16:30Z, until=16:53Z)` call with `nativePastLog.returnedRowsInspected=0`, `matchedRowsReported=0`, `sourceRowsReported=16893`, no cursor and no truncation. The first two counts establish **zero matching messages returned by that query**. The last is the upstream raw source response size **before** the time filter, not proof that 16,893 messages existed in the incident window. Hub Events independently verified the 16:41:40 critical-memory reboot warning followed by the 16:52:15 startup. The original memory consumer remains unknown. The user-visible next check wrongly asked to examine the returned time-bounded messages even though none were returned.

## General correction

- Ordinary Ask and dedicated incident reviews distinguish an actually inspected *empty filtered page* from a successful summary-only request or a non-empty message page. They report the raw-source pre-filter count separately from the returned filtered count, retaining bounded numeric page observations in Technical JSON.
- A zero-match page does **not** certify full retention, absence of historical events, failure of the parser, or causal responsibility. Next checks point to a separately scoped read-only verification of source retention/timezone and any locally retained diagnostic journal rather than inventing a culprit.
- Preserve the v0.18.438 historical typed-message receipt, v0.18.437 chart improvements, explicit Hubitat critical-memory reboot warning, and distinction between trigger and original pressure source.
- New regression fixtures cover an empty page with 16,893 pre-filter rows, a positive/empty mixture, and unsuccessful or summary-only receipts. No real old log content has been fabricated.

## Measurement and safety

The v0.18.438 sample reported 57.2 seconds displayed, 8 model rounds and 6 executed tools with 2 blocked invalid mode/time attempts; descriptive only. Complex investigations have **no numeric latency acceptance target**. No new MCP calls, polling, provider changes, writes, local archive data, hub/router changes or runtime deadline changes.

CI green is a necessary release gate, **not measured improvement in live model answer quality**. The original memory consumer and actual retention horizon remain unverified. Roll back on wrong source-class promotion, private message leakage, current-state regression, incorrect empty-page assertion or failing integration tests. Live retest requires full answer and Technical JSON; compare source-qualified next checks rather than speculative causes.
