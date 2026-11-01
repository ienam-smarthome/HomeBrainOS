# HomeBrainOS v0.18.315 — Stage 8 read-only live shadow preflight

## Objective

The consented Ollama Cloud synthetic Stage 6 v0.18.314 mesh-plug benchmark successfully recovered all three relevant sources (3/3), matched declared atoms 10/10 with no mismatches, and gave a cautious answer within 7.7s and four Cloud calls. This establishes useful **fictional evidence planning and output-format compliance**, not real Hubitat incident correctness, independently verified prose or production publisher readiness.

Stage 8 creates a safe **first step** into real-device validation, without prematurely connecting the experimental synthetic investigator to production device control or live evidence publication.

## Phone UI

A new **Live Shadow · Read-only preflight** panel accepts one numeric Hubitat device ID and a **fresh per-run consent checkbox**. The button stays disabled until both are supplied. A run uses a new dedicated, same-origin, JSON-only POST endpoint `/api/live-shadow/preflight`; it requires explicit `confirm_read_only=true` and `x-homebrain-live-readonly: confirmed` with cross-site requests rejected. The checkbox resets after each run.

The handler performs only a bounded call to the existing Hubitat **resources/read hubitat://context** resource. There is **no Cloud AI request**, model routing, MCP tool calls, writes, actuator commands, app/driver inspection, archived log access, raw event export, persistence or modification to production answer publishing. Reading the context is a real local network read; it may obtain a whole-hub snapshot inside the service, but the response projects **only the requested single device**. No raw context is returned.

## Evidence boundary

The pure projection:
- Requires explicit complete identity coverage, numeric total count, nontruncated/nonnull device list, one exact ID match, and a usable state map.
- Exposes a small allowlist of reported state fields (switch, healthStatus, mqttStatus, sensorStatus, power, battery, selected thermostat values) with bounded primitive values; drops names, rooms, IP/MAC addresses, raw log/message/error text, access tokens and arbitrary attributes.
- Identifies `reported` status and the preflight's own collector timestamp, without asserting original device event time or trustworthy source clocks.
- Explicitly states that MQTT connection is not physical device liveness, that current state is not history, and that no unique cause, command execution, global absence, or actuator outcome can be established.
- Rejects partial or ambiguous identity snapshots rather than making a confident statement from missing data.
- Never returns automatic publisher approval. No uploaded or persisted capture and no additional Ollama requests.

## Test plan

CI mocks Hubitat; it tests UI opt-in, same-origin/consent and input validation, a single read of complete context, blocked missing/incomplete/ambiguous inventory, removal of sensitive fields, no Cloud transport call, and production publisher isolation. **No live Hubitat test is performed by CI.**

### Live manual acceptance — phase 1

After updating the add-on on the phone, open **Live Shadow · Read-only preflight**, enter a **numeric device ID** (e.g. a plug known to the user), authorise one context read and inspect reported states. Confirm device identity, transport-vs-device state distinctions and any completeness blocker. Share the response/status for review **before** enabling any later AI-driven read-only historical investigation. The current feature does not run the Stage 6 synthetic Gemma investigation on real data and does not enable a redesigned publisher.

Rollback: revert this PR and restore v0.18.314.