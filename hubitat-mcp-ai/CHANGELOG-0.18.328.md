# v0.18.328 — Stage 9.3 upstream Hubitat app-log response contract

## Live basis
On 1 November 2026, Hallway Light 1 (7829) had an independently reverified command-off by app 4012 at 15:15:13.140 UTC, followed by an OFF report at 15:15:13.290 UTC. The separately consented app-log call was attempted, but Stage 9.2 returned `app_log_payload_unusable` and no rows.

## Root cause identified in upstream source
The official kingpanther13 Hubitat-local-MCP-server implementation of `hub_get_logs` defaults to `mode="past"` and returns paged `entries` (with `count`, `mode` etc.), not the `logs` array the old shadow projector required. Its `time` can be a hub-local wall-clock string lacking an offset. The upstream server also supports `status="in_progress"` when snapshots are still being gathered. These are all concrete supported shapes from `libraries/mcp-diagnostics-lib.groovy`, not invented alternatives.

## Fix
- Set explicit `mode="past"` in the existing fixed read-only `hub_get_logs` request.
- Accept upstream `entries` and previously supported synthetic/legacy `logs` after bounded unwraps. Reject unrelated modes and malformed envelopes rather than silently accepting them.
- Distinguish `app_log_source_in_progress` from an empty page or unusable payload. No automatic additional reads.
- Only admit source records with acceptable app type and no conflicting explicit app ID; preserve `backend_filter_only_unverified` when source rows have no per-row app ID.
- For offset-aware timestamps, validate the ±2-minute UTC window. For real Hubitat past-log hub-local timestamps without a timezone, preserve the formatted local time separately, never fabricate an authenticated UTC clock or command-to-log offset; the time filter was already applied server-side.
- Retain existing privacy projection: only safe classification strings, bounded timestamps, identity basis and aggregate counts are published; never raw messages, app names, credentials, or arbitrary labels.
- Update mobile display to label local vs UTC time and explain pending reads without claiming no app activity.

## Safety and tests
- No device commands or Cloud inference; no change to journal capture, app configurations, source retention, production publisher or user consent.
- Regression tests use upstream-shaped `entries`, empty pages, nested `in_progress`, mismatched row identity, privacy canaries, synthetic legacy fixtures, and mobile clock labels.
- Phone acceptance: update to v0.18.328, use Command Shadow for 7829, select the fresh 15:15:13.140 UTC OFF command if still present and within 48h, consent separately, then copy the combined test results. `app_log_source_in_progress` does not prove no logs. A completed but empty/unclassifiable page still does not prove no action.

Rollback: revert this PR to v0.18.327.
