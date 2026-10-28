# HomeBrainOS v0.18.190 — Historical warning-window provenance

## Live regression (28 October 2026, v0.18.189)

The model resolved Google Nest Hub 7934 and made eight successful reads
in 19.985 seconds. It retrieved the same 71 historical WARN rows already
known (43 sampled runQ, 27 excessive hub-load and one setVolume rows).
It read **10 recent device status events, from 19:33:33 to 19:55:19**,
but the slow-method warnings occupied an earlier incident window:
runQ 17:04:48–17:58:24 and setVolume at 17:42:22.697. The event read
had issuer_apps=[] and no command events. V2 incorrectly reported
causal_coverage_gap=null merely because an event-history call succeeded.
It also re-queried narrower subsets of WARN rows already present in its
initial 71-row sample and reread an identical device state.

## Shared investigation fixes

- **Historical window integrity:** The evidence-coverage checker now
  compares the actual returned device-event timestamps with the
  slow-operation WARN group windows. Events acquired from a later
  newest-first page never establish coverage of an earlier incident.
- **Source-grounded follow-up:** The host derives the slow-method name and
  timestamp from typed WARN evidence, not the user's wording. At an
  investigation budget boundary, it gives the model at most one additional
  opportunity to select an authorised history read with relevant
  hoursBack/limit/attribute filters (for example
  attribute=command-setVolume, hoursBack=48). No extra Hubitat call
  happens without the model selecting the read.
- **Issuer vs status:** Device-generated status records are not proof
  that app-issued commands were or were not present. A command event is
  only a temporal/caller association; source-clock timezone alignment
  and causal direction remain unverified.
- **Duplicate warning groups:** A narrowed log call wholly contained by
  a prior identical warning group/time range provides no new
  observation. It remains in source receipts but is flagged to the
  model as redundant, unlike newly extended warnings or different
  message groups. Duplicate snapshots retain their own existing
  circuit breaker.
- **Coverage transparency:** Event summaries retain oldest/newest
  sampled timestamps, sampled row count, and app-issuer count.
  Native diagnostic read filters now include hoursBack and attribute.
  Any unresolved warning-window/issuer gap is reported in the user
  answer and validation_issues rather than silently shown as complete.
- All calls remain read-only, subject/issuer identities continue to
  require independently attested namespace IDs, raw private speech
  content stays excluded, and production Main Ask is unchanged.

## Tests and limits

Tests replay the exact old-warning/newer-status-window scenario,
demonstrate one optional model-selected command filter returning
typed app issuer identity, detect subset log repetition, and confirm
that an unresolved earlier incident window is prominently disclosed.
Historical log and device-event windows can still be truncated or
unavailable, and the host does not prove timezone equivalence or
root cause. The real cause of Google Nest Hub runQ/setVolume delays
cannot be verified without independent driver execution/source
evidence. Live acceptance follows repository CI.
