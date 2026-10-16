# 0.17.91 — Whole-hub audit evidence contracts and telemetry-source calibration

## Live findings (three 16 October 2026 read-only outputs)
- A comprehensive System Check examined 207 devices, 152 apps/rules and 200 sampled logs, but the shared completion layer mislabeled the broad hub-health report as a `causal_provenance` investigation, with `device_history` and `command_history` called missing. These historical per-device causation requirements do **not** follow from a whole-hub audit question.
- An independent model-led Hubitat performance audit checked hub metrics, top-20 performance rows and sampled logs, but did not read device availability. It needs explicit source-scope accounting for device health, rather than an irrelevant per-device historic initiator requirement.
- The Bedroom 3 Mesh diagnosis recorded repeated watchdog no-data warnings up to 39,018 seconds, but assigned high confidence to a guessed application-layer failure, interpreted `mqttStatus=connected` as a verified active broker session, and treated `lastSeen` as an independently verified last physical packet.
- A model-led performance answer restated its exact OpenWeatherMap hypothesis in an immediately nested bullet. The 0.17.90 duplicate checker handled standalone paragraphs, not this duplication.
- Performance cost remains significant: the comprehensive audit spent 27.0s acquiring/classifying the device inventory and a separate performance read took 18.9s. These are wall-clock **source retrieval** times, not proven CPU load; no speculative Hubitat load optimisations are included in this release.

## Changes
- New `system_audit_coverage.py` chooses source requirements from the actual execution route and question: section availability for whole-hub health, hub metrics/performance/logs plus specifically requested device/automation checks for model-led performance. The shared completion layer applies it **before** generic individual-causation classification.
- Bounded log samples remain explicitly bounded. Unread sources are identified and do not become blanket health or fault verdicts; already checked general audit sections are not described as absent individual device-command reads.
- General telemetry claim calibration now covers bold-colon confidence syntax and unverified MQTT broker-session, transport-recovery and last-successful-physical-telemetry claims **only when current-turn device-scoped watchdog evidence is actually present**. It preserves the real watchdog interval observations and does not replace them with an assumed physical cause.
- Duplicate removal now eliminates immediately nested bullet restatements of a parent's evidence claim while keeping nonduplicate nested actions, legitimate parallel lists and raw history tables untouched.

## Remaining work
- Diagnose and optimise the independent slow MCP inventory/performance retrieval paths without overloading Hubitat.
- General, stateful multi-hypothesis reasoning still needs evidence-value ranking. This release fixes source-class obligations and statement honesty rather than introducing a new agent that invents missing capabilities.
- Read-only. No device writes, Hubitat settings changes, cloud account changes, journal schema migrations or unsolicited command tests.

## Testing
Cross-domain fixtures from the three real outputs plus the entire existing Python suite, add-on tests, metadata and container smoke tests required before merge.
