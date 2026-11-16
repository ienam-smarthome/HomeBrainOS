# HomeBrainOS V2 alpha.130 — native device-history envelope compatibility

**Status:** merged [PR #1696](https://github.com/ienam-smarthome/HomeBrainOS/pull/1696) at `787728599c0abc380dbdef99c3714aca7e0c1b00` after **4/4 exact-head CI workflows green**; installed source-real alpha.130 acceptance remains unmeasured. V2 only. No V1, live heating
scheduler, hub settings, physical device, model route, read-only source
selection, write approval or other action safety changes.

## Source-real alpha.129 first-answer regression (PRIVATE, 16 November 2026)

One installed natural, read-only WHY question used 4/4 successful MCP reads,
8 model rounds, about 469k provider-reported prompt tokens and 33.4 s.
The model reached an event-specific command → reported-state chronology and
read the relevant app's real past execution log in the source-review path.
But final causal publication claimed `controller_decision_unverified` and
replaced the answer with a misleading *no verified event history* notice.
No fallback device event rows survived, despite a 50-row native history.
Live quality **1/8**. Raw private household logs and identifiers are NOT
included in the repository.

## Root cause: original upstream response shape

The installed `hub_list_device_events` response uses the legitimate
legacy/compact envelope `{"device": label, "events": [...], "count": n}`
and *does not echo* the `source="device"` or `deviceId` keys. The original
successful MCP tool arguments contain the executed device ID. Alpha.129's
causal-publication source check required `source="device"`, and alpha.127's
source-only fallback required *both* explicit fields. This was a mistaken
contract assumption rather than an actual upstream read failure.

## General correction

- Shared `native_device_event_receipt.original_device_event_history`
  validates the executed successful native read, exact tool name, original
  requested device ID, a device-history response shape, valid event rows,
  and any optional echoed ID/source. Either explicit or legacy device
  response can be accepted; contradictory source or device ID fails closed.
  App-event-only reads, arbitrary unlabelled objects and non-device
  sources cannot masquerade as device history.
- Both the causal publication *source-category* check and the bounded
  state-history partial renderer now use the same identity contract.
  The application-log source still must match an original recorded
  `producedBy.appId`; `triggered[]` listeners and unrelated/empty logs
  cannot establish it. A matching log is necessary evidence type, NOT
  sufficient proof of an event-specific causal decision.
- Safe partial answers preserve original device state/time observations
  even if final model prose is rejected. Never invent a missing physical
  effect or replay an unsound earlier model draft.
- Fictional unit and end-to-end tests cover both native shapes, a positive
  actual matching app-log read, mismatched IDs, unrelated/empty logs,
  missing device identity, bounded state fallback, source immutability
  and no native writes or added AI rounds.

## Acceptance

The fix should prevent a *false publication downgrade*, not be treated as
proof that the AI's causal explanation is accurate. The model still selects
tools and must inspect the event-time controller decision independently.
After green exact-head CI and installing alpha.130, ask an uncoached
read-only WHY in a fresh chat. Verify that the answer distinguishes the
reported output event, original setpoint/command producer, actual
event-time room or input demand in app execution logs, precise
chronology, bounded history coverage and physical unknowns. Report
`causal_claim_verification`, fallback status, original receipts, rounds,
tokens and latency. Do not count synthetic tests as an installed 8/8.
