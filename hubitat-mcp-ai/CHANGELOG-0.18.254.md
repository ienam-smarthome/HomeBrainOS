# v0.18.254 — Cross-source historical incident reconciliation

## Observed live failure

v0.18.253 successfully recovered 20 original-source-timestamped Bathroom light switch observations from the Historical Journal, plus 20 collector-only receipts. The same investigation had independently read Shower Light device 7807: ON at 15:07:32.530, app 4014 `off()` at 15:11:45.944, OFF at 15:11:46.134. Nevertheless, its journal-based final digest omitted the Shower Light and falsely stated that no source-timestamped switch history existed for it.

## Fix

- The original unified agent's existing `source_incident_digest` now combines Historical Journal source-time switch observations **with independently source-timed native Hubitat switch reports for targets that lacked archived source-time coverage**.
- Maintains a single chronological multi-device timeline and marks which edges come from direct Hubitat device-event history.
- Never double counts native and Journal source-time rows for the same target; native reports are added only for targets absent from source-time Journal recovery.
- Source-count and reception-only-count remain truthful and separate. Collector arrival records never become source timestamps.
- Per-target missing-history claims use the **union of verified sources**, not just Journal contents.
- Direct Hubitat OFF commands remain distinct from subsequent state reports, with singular wording when one command is shown.
- Adds cross-domain regression cases for a journal-recovered pair and a third device with live ON/OFF plus a command, mixed-source deduplication, legitimate missing sources and collector-only edges.

## Scope

Read-only explanation/verification change; no new MCP operations, no writes to Hubitat/Home Assistant and no additional model route. The upstream initiator remains unverified unless independent source-command evidence exists. All GitHub Actions checks are required before merge.
