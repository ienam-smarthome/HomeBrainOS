# HomeBrain v0.17.66 — command clues and cached telemetry consistency

- Keep the strict two-second command-to-state causal attribution threshold.
- Identify 2–30-second, identity-scoped command precursors for the exact requested boundary as *investigative clues*, not verified initiators.
- Supply those clues to causal synthesis to avoid overlooking a documented preceding Hubitat command.
- Detect contradictions between driver `lastSeen` and `dataAgeSeconds` at a timestamped targeted read; explain that neither proves current physical connectivity.
- Add synthetic regressions from Livingroom Light 1 and Bedroom 3 Mesh live diagnostics.

All investigation paths remain read-only. Automation topology discovery and stronger final-response synthesis are separate future improvements; this release does not establish live causation.