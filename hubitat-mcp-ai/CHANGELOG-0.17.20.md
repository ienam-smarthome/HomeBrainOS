# HomeBrain 0.17.20 — Focal historical sensor coverage gate

- Detects when local sensor-event pages do not include any history at or before the requested OFF event, avoiding false causal conclusions from newer-only returned rows.
- Skips costly unrelated cross-room adaptive reads when the limiting factor is unavailable local prehistory, rather than pretending extra searches can restore missing records.
- Carries the local historical coverage assessment into the causal evidence graph and model's pre-synthesis answer plan.
- Explains source limitations: missing past rows cannot prove no inactivity, rule execution, Hue action, or Hubitat command.
- Protects the final answer from unsupported external-only and Hubitat-listener-only conclusions when focal historical coverage is missing.
- Adds regression tests for paged-out focal readings, retained pre-focal readings, missing local pages, and idempotent source-scoped claim validation.
- Read-only change: no Hubitat devices, automations, or settings are altered.

Note: Hubitat MCP's historical device-event API currently has no reliable start/end filtering. This release handles missing historical coverage honestly; it cannot recover an event the source no longer returns.
