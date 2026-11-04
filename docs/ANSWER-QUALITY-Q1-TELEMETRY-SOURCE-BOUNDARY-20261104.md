# Q1 device-telemetry explanation source boundary — 4 November 2026

## Installed user observation — HomeBrainOS v0.18.402

Frozen registered read-only `device_mqtt_conflict` question:
`Why does Bedroom 3 Mesh show MQTT connected when its health is offline?`
Gemma4:31b via Ollama free returned an **unresolved** result in
**36,507 ms** (provider 29,747ms, 6 model rounds, 8 tool calls).
Current typed state for target device ID 7103 reported
`healthStatus=offline`, `mqttStatus=connected`, a stored Oct 12
`lastSeen`, and `dataAgeSeconds=162325` (about 45.1 hours).
The host's existing source-clock check computed **566.1 hours**
from the lastSeen date versus **45.1 hours** from reported age,
`sourcesAgree=false`, `physicalTelemetryProven=false`.

A bounded history returned **15 events**, including positive
`mqttStatus=disconnected` and later `connected` reports from Nov 3.
The model nevertheless said no disconnect message had been
received, that the MQTT status was proven stale due to the
driver's precise update semantics, and that `healthStatus` was
a live watchdog calculation. It also called the device physically
offline and the Oct12 / 45h metadata last actual telemetry.
Detailed source-class logs were queried, but the published
receipt only retained the log-response field names, not typed
watchdog decisions or method bodies.

The **same host coverage** explicitly reported:
`rootCauseVerified=false`,
`sourceAuthority.verifiedInstalledDriverBehaviour=false`,
`independentBrokerPacketsVerified=false`,
`incidentReasoningDepth.driverMethodBehaviourVerified=false`,
and `questionResolved=false`. This makes the final causal
narrative inconsistent with its independently computed coverage.
The device could have no fresh endpoint telemetry while a
broker/session attribute says connected; that is a plausible
explanation, not a proven physical failure or driver mechanism.

## Reusable correction, not an incident-specific driver workaround

`telemetry_source_claim_guard.py` adds an evidence-derived
publication contract after the host's source-coverage assessment.
It operates only on scoped read-only device-telemetry investigations
and requires the same target device ID. It leaves model-authored
observations and qualified hypotheses in place, but replaces
unsupported categorical physical failure, unexplained internal
driver/watchdog calculations, verified last-packet ages, and
absolute no-disconnect assertions with short, source-grounded
qualifications. A positive disconnected event can refute
blanket absence even when the returned history is bounded.

The guard reuses current request typed receipts and the existing
`telemetry_clock_consistency` analysis. It does NOT inspect
Hubitat driver code, invent new packets/log entries, trigger
reconnections, collect more logs, issue commands, add model
rounds or declare actual root cause. It only reports correction
categories and count to the local request metrics/coverage.

## Objective measurement and rollback

Before: **36.507s**, 6 rounds, 8 calls, confident source-
unverified driver/physical explanations, conflicting clocks
unacknowledged, overall `unresolved` correctly displayed.
After installation: **NOT MEASURED**. Exact-head CI and
synthetic tests cannot certify Gemini/Claude parity, physical
network health, first-attempt correctness or a lower response
time. Check new `telemetry_source_claim_repairs` and
`investigation_coverage.telemetryPublicationCorrections` on a
read-only cross-domain telemetry explanation; inspect whether
model prose remains useful without speculative mechanisms.

Rollback if the shared checker changes unrelated questions,
attributes another device's events to the target, discards
properly verified installed driver-code findings or leaks
identifying source details. The original Q1→Q2→Q3→Q4
Answer Quality charter remains authoritative.
