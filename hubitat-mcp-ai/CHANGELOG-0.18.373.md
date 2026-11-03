# HomeBrainOS v0.18.373 — Q2 strict native event-role admission

## Hypothesis and scope

A source-role check used for the final model context and causal validation accepted
`homebrain_device_history.details.observedEvents/boundaryEvents` but did not
accept `hub_list_device_events.details.events`, even when the native receipt
was already successful, read-only and tied to a verified device ID. It also
understood `producedBy.appId` but not the native, typed
`producedBy={id,type:"app"}` form. As a result, native event evidence could be
missing from the model's source-role briefing and from the final provenance
check. This is a generic cross-integration identity/coverage defect, not
evidence of which controller acted in a particular household incident.

## Change

- Read native `details.events` only for an exact `hub_list_device_events`
  receipt that has already met the existing success, read-effect,
  device-ID and live-claim gates. Preserve the deterministic history shapes.
- Normalize a producer from an explicit role ID or the *typed* native
  `{id,type}` form; reject untyped and conflicting IDs for apps,
  reporting devices and downstream listeners.
- Preserve separate evidence graph edges: issued-command, reported-state,
  and notified-listener. Do not treat a bridge-reported `physical` state
  event as proof of a wall press or external command; an empty bounded
  command result cannot prove global absence.
- No tool/planner/prompt round added, no new source access, no write pathway
  or local private evidence persisted.

## Measured offline before/after and limitations

**Synthetic evidence-admission regression only**: under the previous
implementation, a native `details.events` receipt of one switch-state
row and one command row had **0** roles admitted by the source-role
parser. The revised parser is expected to admit **1 reported state and
1 recorded command** with distinct typed producer roles, plus one
listener. The new CI tests check this directly, including invalid
identity, empty, mismatched, unscoped and cross-domain negative cases.
The integration test checks that the shared synthesis validator now
receives those normalized roles.

This is **not** a before/after real model-answer grade. Evidence parsing is
not semantic attestation of every model sentence, and finite narrative
guards, including Markdown table handling, remain incomplete. First-answer
factual grounding, usefulness, latency and Gemma-vs-alternative improvement
are **NOT MEASURED**. The observed installed Gemma causal overclaim is not
claimed solved. The earlier 180s MQTT timeout is not source-diagnosed by
this change; the separate v0.18.372 bounded-read fix remains in place.

## Verification and rollout

Require all exact-head PR CI checks and full release assurance to pass
before merging. This work does not touch Home Assistant or Hubitat.
After optional installation, request **one** read-only HomeBrain first
answer plus Technical JSON for a frozen case; do not count unmatched
live evidence as an A/B. Avoid repeated live requests or new Cloud
spend solely for this source-role regression.

**Rollback:** Revert the bounded native event-row ingestion and typed
actor-ID normalizer, restore v0.18.372 package metadata and previous
release index. No data migration or hub-device changes are involved.
