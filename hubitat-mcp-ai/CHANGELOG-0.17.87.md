# 0.17.87 — Evidence-faithful cross-domain investigation recovery

## Live regressions addressed

1. **Open-ended incident investigation:** In v0.17.86 the model retrieved source-scoped Bedroom 2 Light events, then drifted to a claim about Bedroom 2 Soft Sensor. The existing device-claim safeguard correctly refused the unsupported name, but discarded all useful evidence. The new `incident_grounded_fallback.py` preserves a **short, receipt-grounded partial report** about the single verified target, with its latest recorded state events and reporter provenance, only when the user explicitly delegates choosing an incident. Named-device questions and multiple conflicting histories still fail closed. Listener/subscriber apps are never presented as command initiators.
2. **Broad automation audit:** A request covering “all my broken, incomplete, disabled or potentially faulty Hubitat automations” missed the comprehensive evidence-rich route due to punctuation and modifier ordering. The population-scope classifier now recognises that phrasing, while leaving single-device event investigations on their own path. Readable rule configurations and false required-expression states alone remain **insufficient to claim successful historical execution**.
3. **Offline MQTT diagnosis:** The v0.17.86 typed-history finalizer replaced a useful device-specific analysis with generic counts, dropping up to 51 scoped logs, including repeated watchdog no-data warnings. `device_watchdog_evidence.py` now extracts only device-ID-matched warnings from the actually returned bounded excerpts and exposes their timing and seconds-since-data progression, explicitly without proving physical cause or successful reconnection.
4. **Command summary:** Zero returned command invocations now prints “No command invocation was returned in this bounded sample”, not the contradictory “Command invocations are recorded.”

## Safety and scope

No device actuation, automation edits, MQTT writes, DB schema migrations, or background polling changes. This does not invent a self-selected event or prove controller causation. The fallback executes only after an actual device-claim mismatch has exhausted its standard retry; it reports source observations, not an explanation the evidence cannot support. Full multi-hypothesis autonomous planning remains a future architectural priority.

## Validation

Regression tests cover delegated selection versus explicit device naming, ambiguous identities, real Bedroom 2 event provenance, multi-modifier automation audit routing, watchdog trend from recorded 27,232-second warnings, device-ID isolation, and zero-command summaries. Full GitHub Python/add-on/container validation and live Home Assistant deployment remain separate requirements.
