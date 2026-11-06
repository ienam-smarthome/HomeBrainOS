# HomeBrainOS 0.18.435 — shared Answer Quality and qualified log receipts

- Ordinary Ask no longer collapses every unresolved causal investigation to a generic rejection paragraph: the host provides safe source-qualified read-only follow-ups, plus authenticated bounded Hubitat system-event facts **only when the receipts include typed event rows**.
- When the causal model draft is withheld, the report retains independent MCP read receipts rather than guessing missing timestamps, app identities or the original memory-consuming process.
- Count successes and attempts separately for `hub_get_logs(mode="hubEvents")`, `mode="past"`, `mode="apps"` and bounded generic log calls. A successful mode request does not prove an app-specific historical message was returned.
- Introduce `causal_read_source_coverage` in guarded ordinary Ask outcomes; add `log_query_modes`, `verified_bounded_app_message_rows` and explicit incomplete historical coverage to dedicated incident Technical details.
- Count an actual bounded app-message row only when an existing successful, read-only, live-supported receipt includes its app ID, message body (not copied into summary), offset-aware source timestamp and matching date-bounded query. Summary-only receipts and unbounded app snapshots count as **zero verified rows**, not as evidence of absence.
- No extra MCP calls, changes to Hubitat/Home Assistant/router, write permissions, paid-model escalation or new polling.
- Regression tests cover the 5 November 16:52 and 22:33 ordinary Ask live patterns, source-time filtering, stale/unverified/mutating receipts, and private message exclusion.

## Important limitations

The previous two user-submitted responses were from `/api/ask`, not from the dedicated `/api/hub-diagnostics/investigate` endpoint. These improvements do not retrospectively authenticate the content of the original returned Hub Events or establish the root cause. If an MCP tool returns only a receipt summary rather than typed content rows, the historical message content and exact coverage remain unverified. Continue to test both routes separately using actual source records; do not claim a live pass based on synthetic tests alone.
