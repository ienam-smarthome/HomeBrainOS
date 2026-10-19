# 0.18.37 — Positive mixed command-history evidence and timezone-correct causality

## Live regression: v0.18.36, 19 October 2026
A read-only Gemma investigation of Bedroom 3 Mesh (device 7103), OFF on 12 October 2026 at ~01:30 BST, recovered a genuine device-event record:
- 01:30:01.743 BST: `command-off`, `producedBy.appId=3950` ("Power saving: Bedroom 3 Mesh off @night")
- 01:30:01.914 BST: reported `switch=off`
- 01:33:46.925 BST: reported `healthStatus=offline`.

Despite that, the generic shared source coverage incorrectly reported `command_history` unchecked because the event came from a **successful mixed device-history page without `attribute=command-off`**. Its app-log query `01:20–01:40Z` targeted 02:20–02:40 BST, an hour after the incident, and returned zero rows. The answer then called a physical interaction "contradicted" and described the 171ms state-report interval as a physical response, both beyond the independent source evidence.

## Architectural correction (not device-specific)
- Treat a successful *target-scoped Hubitat device-event read* with an actual typed, dated `command-on/off` event as **both device-history and command-history source classes**. Do not grant command coverage to empty pages, mere switch transitions, failed reads, mutation receipts, or model narration.
- Derive the event's UK local time with `Europe/London`, validate BST/GMT against the date, and include its UTC equivalent and a suggested 10-minute bounded log/event read interval in the model's existing system prompt before it chooses tools. Reject mismatched/ambiguous clock forms; do not fabricate event times.
- Independently assess whether app-log requests for the recorded command issuer encompass the requested incident in UTC. Inaccurate / empty windows do not establish the absence of execution logs. Surface a distinct `incidentAppLogWindow` field and clear text where the actual window missed the incident.
- Where a unique event with typed app `producedBy` matches the requested date/time/action and target, expose `recordedCommandProvenance` (the recorded app issuer) while maintaining **deliveryVerified=false, physicalActuationVerified=false, upstreamTriggerVerified=false**. Do not equate app-issued commands to physical acknowledgement or rule-trigger verification.
- At the shared final evidence gate, conservatively repair specific model overclaims about excluded physical/external actions and physical acknowledgement, while keeping the genuine observed event timeline and expressly separate root cause from the known command producer.
- Retain existing `unresolved` outcome for causal questions with truncated history/unchecked independent mechanisms. No Hubitat state changes, additional tool permissions, or cloud routing/billing changes.

## Validation
Regression tests reconstruct the exact original event rows, cover mixed versus filtered command reads, malformed/wrong-target rows, competing producers, timezone arithmetic, misleading zero app logs, correction of overclaimed model prose, full API source-coverage metadata and no device controls.

Merge only after all 3 GitHub CI workflows pass. Live verification on the updated add-on is separate. Next architectural priority: reduce repeated model planning rounds when authoritative command evidence is already sufficient for the narrowly verified subquestion.
