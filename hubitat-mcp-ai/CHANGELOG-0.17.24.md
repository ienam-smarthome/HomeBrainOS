# HomeBrain 0.17.24 — Recover historical bridge provenance after recent boundary truncation

- Corrects a live 0.17.23 failure where the target 08:18:23 OFF was present in the subject's `temporalAnalysis.observedIntervals` and `correlationEvents`, but absent from its newest-three `boundaryEvents` subset. This prevented the deterministic reporting-source secondary investigation from running.
- Producer correlation now prefers `boundaryEvents` and also considers retained historical `correlationEvents` from the same successful, exact-subject `homebrain_device_history` receipt. Only genuine switch on/off rows with timestamps enter the candidate pool.
- The existing interval-boundary alignment and event-time tolerance still gate attribution. An external Matter/Hue bridge remains a **reporting source**, not proof of the initiating command.
- Preserves the 0.17.23 explicit-event anchoring. A later OFF must not replace the requested event.
- Adds regression tests with the live trace's trimmed presentation events, historical correlation row, another later OFF, and the actual orchestrator prefetch-to-secondary handoff.
- Historical `since`/`until` sensor retrieval remains conditional on its capability and coverage gates. If upstream historical events were discarded, their absence must not be interpreted as inactivity or proof of a particular automation.
- Read-only: no devices, Hubitat apps, automations, or hub settings are modified.

**Live verification:** Retry the 08:18:23 Bedroom 1 Light OFF question with HomeBrain 0.17.24 and inspect `causal_reporting_source_correlation`, `focalWindowRetrieval`, actual sensor-window arguments, tool calls, and model rounds. CI does not establish upstream history retention.
