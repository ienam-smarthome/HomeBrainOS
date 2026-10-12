# HomeBrain 0.17.22 — windowed history telemetry and integration hotfix

- Registers `causal_focal_window_reads`, `causal_focal_window_evidence_recovered`, and `causal_focal_history_gap_stop` in the strict request metric allowlist. An unregistered metric otherwise throws a ValueError during a windowed history retrieval or retained-history fallback.
- Adds full-orchestrator tests proving that HomeBrain uses only the two relevant local sensor windows when the recent page does not reach the historical OFF event.
- Verifies that current MCP Rule Server responses with echoed `sinceMode`, `sinceTimestamp`, `untilTimestamp` restore actual retained evidence, and that an older server ignoring those fields safely leaves historical source coverage unknown.
- Keeps device actions, automations, settings and history stores untouched; read-only integration correction.

Install this release rather than 0.17.21. The earlier 0.17.21 PR auto-merged before the newer orchestrator tests exposed the missing metric registrations.
