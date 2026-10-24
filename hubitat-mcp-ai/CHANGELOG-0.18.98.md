# HomeBrainOS 0.18.98 — Reconcile incident timing evidence and diagnostic depth

## Live regression (24 October 2026)

The installed 0.18.97 Bedroom 3 Mesh (device 7103) read-only test correctly chose the device-connectivity investigation but still finished unresolved after 11 free Gemma model rounds and 16 MCP/local tool calls (approximately 71 seconds). It retrieved a complete reported driver code span (code ID 3686) but did not verify relevant method behaviour, did not verify the controlling automation, and did not retain evidence of upstream connectivity. The safe final formatter replaced much of the AI's response with a generic telemetry report.

The read-only receipts contain a useful clue: a watchdog warning at 2026-10-24 15:46:55.109 reports 71,898 seconds without data; subtracting that duration yields 2026-10-23 19:48:37.109, the exact local time of a device-attributed MQTT-disconnected event. Other watchdog warnings derive the same reference time within subsecond rounding. This *suggests* a software watchdog counter reset/reference at the MQTT state transition, but does not establish a physical last-packet time or root cause.

## Improvements

- Derive elapsed watchdog reference times from multiple independently dated, device-ID-scoped warning rows; compare with same-device typed event history only when calculated references are consistent and event times align. The safe final report and structured coverage expose the alignment with explicit local-clock and physical-causation limitations.
- Introduce independent incident-depth assessment: distinguish raw driver source retrieved versus actual verified method logic; app inventory versus identified controlling automation and relevant stored configuration; and a generic network-health call versus actual identity-linked upstream observations. A successful MCP call alone cannot close these gaps.
- A device event/history/status source-class checklist no longer masquerades as a completed root-cause investigation; unresolved discriminators remain visible in the final result.
- Strengthen model-directed read-only follow-up instructions: infer timer references, verify driver timestamp read/write/update paths in the returned implementation, inspect actual device dependents/controlling automation, and refuse to infer network status from unreturned probe results.
- Regression tests reproduce the 0.18.97 timestamps and tool receipts, counterexample devices/misaligned timing, source retrieval without source interpretation, and final structured coverage.

## Limits and safety

The inferred software counter reference is conditional on event and native log timestamps representing the same local clock. The observed alignment does not prove physical presence or disconnection, and the source has not been re-analysed on the live Hubitat installation. Native read-only test replay is required to evaluate the next improvement. No Hubitat devices, rules, settings or paid model tier changed.
