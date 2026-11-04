# Q1 device-telemetry source saturation and ID fidelity — 4 November 2026

## User-observed v0.18.403 paired live regression

Frozen registered Q1 `device_mqtt_conflict` question:
`Why does Bedroom 3 Mesh show MQTT connected when its health is offline?`
Installed v0.18.403 returned an `unresolved` but source-qualified
explanation in **42.635 seconds** (**8 Gemma free rounds**,
**13 tool calls**, provider 35.241s). The published answer
correctly distinguished Hubitat-reported healthStatus=offline
from MQTT connected, and the conflicting stored lastSeen and
dataAgeSeconds clocks (**566.8h** versus **45.1h**).
The source-boundary applied **2 repairs** (`telemetry_driver_
claim_unverified`, `telemetry_physical_claim_unverified`),
and model-first draft was NOT published unchanged;
`modelFirstRejection=model-draft-provenance-changed` and
`publicationBoundaryShadow.replacementPerformed=true`.

Compared with installed v0.18.402's same-question run
(**36.507s**, 6 rounds, 8 calls), this one response was
**6.128s slower** with 2 additional model rounds and
5 more tool calls. These are separate source observations;
there is no controlled before/after latency distribution
or established causal attribution for the slowdown.

## General source-routing and completion defects

The read-only telemetry coordinator already recorded status,
bounded history and scoped logs. The question's core status
discrepancy is answerable provisionally by comparing
source-derived clocks and preserving unknown physical cause.
Yet the loop required a separate source discriminator or
offered checkpoint, promoting repeated model-driven discovery.
After source reads, the model attempted
`homebrain_read_groovy_source(appId=7103)` and
`hub_get_app_config(appId=7103)` even though the source
identity **7103 is a Hubitat device instance**. Neither
operation proved the installed driver's source. There were
also unsuccessful device-dependency reads and a later
configuration read. The existing source evidence itself
reported `rootCauseVerified=false`,
`verifiedInstalledDriverBehaviour=false`, and
`independentBrokerPacketsVerified=false`.

## Candidate v0.18.404 — general, bounded correction

- The shared single-target telemetry stop now recognises a
  narrow evidence-sufficient provisional case when the
  checked device shows explicit `healthStatus=offline`,
  `mqttStatus=connected`, a same-device bound event page,
  a verified scoped log read, and a typed, independently
  inconsistent lastSeen versus data-age check. Require an
  actual question contrasting MQTT and offline statuses.
  This is a **bounded answer opportunity**, NOT a physical
  fault or driver-source proof. Cross-device, write,
  source-code and Rule Machine objectives retain their
  existing completion and permission paths.
- A source-class call failing inside the same round does
  not invalidate an otherwise fully attested set of
  necessary read receipts. Still require one new successful
  read and no mutation to stop after a tool round.
- General source-app identity guard refuses a Groovy app
  workbench or app-configuration read that substitutes
  the target device ID as an app ID without a typed
  same-device dependent-app link. It does not block
  legitimate linked app IDs, verified driver source IDs
  or other device-specific read-only diagnostics.
- Synthetic tests cover source completeness, clock status
  distinction, identity, one successful read with failed
  optional companion, no new reads, cross-device requests,
  and explicitly verified same-numeric-ID app relationships.

## Release and follow-up limits

Before: **42.635s, 8 rounds, 13 tool calls**. After:
**NOT YET MEASURED LIVE**. CI asserts policy contracts but
does not prove p95 latency improvement, model first-draft
accuracy, physical offline status, MQTT broker packets
or full driver watchdog code. Repeat exact registered
read-only Q1 question once after install, inspect actual
rounds, successful/failed reads, source clocks and
`telemetry_post_read_sufficiency_stop` counter. Avoid
repeating this device after paired acceptance: continue
to a different Q1 domain and then same-evidence Q2
model evaluation. No Hubitat/HA/router/device writes.
