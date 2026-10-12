# HomeBrain 0.17.16 — Evidence-complete unresolved investigations

## Root cause and live regression

The 0.17.15 live Bedroom 1 ON+OFF investigation took 14.8s/21 tool calls/one model round, correctly finding the OFF producer unresolved. The separately worded **why-OFF** question took 49.7s/48 tool calls/**10 model rounds**, including 10 irrelevant cross-room occupancy reads. It had already obtained the light's bounded command-off history (two older commands, none aligned with the 08:18:23 OFF), the app's OFF-window logs and configuration, and the local FP300/Soft Sensor histories. Its answer still stated that no Hubitat app could be involved and presented FP300 → external automation → light OFF as a likely causal chain without evidence.

The one-pass synthesis guard required arbitrary surface-form keywords such as “alternative” or “manual”. The user's “possible external causes” lacked them, preventing completion despite equivalent semantic intent.

## Shared architectural changes

- **Typed causal source completion** (`causal_completion_policy.py`): evaluates ON and OFF separately against uniquely observed state transition, relevant bounded command-history, app configuration, event-window logs and local sensor investigation. A complete investigation may have **no identified initiator**. User phrasing chooses the requested ON/OFF direction but cannot block completion simply because it omits a synonym. Explicit mode-history needs remain respected; incomplete/missing source classes remain visible.
- **Source-aware search budget**: if the requested OFF has actual locally checked inactive-sensor correlations near that exact boundary, do not expand an additional batch of unrelated cross-room motion/presence sensors. This is *sufficient evidence for an explicitly unresolved explanation*, not proof that sensor inactivity caused OFF. When local evidence is absent or outside its timing window, capability-grounded broader search remains possible.
- **Shared narrative + table certainty contract** (`causal_certainty_contract.py`): compares OFF causal claims against the same graph-backed proof obligations. Corrects unsupported categorical statements that bounded missing command/log rows rule out Hubitat apps or physical actions; rejects unsupported “likely external” actors or sensor-to-automation causal chains. Applies to Markdown summaries and tables, including a mixed ON/OFF row table; the known ON dimmer hypothesis is preserved. The existing verifier runs during synthesis and at final API serialization.
- **Avoid repair loops**: ON/OFF graph completeness now allows deterministic source-backed local corrections without calling the provider for another wording pass. All corrections remain auditable by the synthesis validation issue metrics.
- **Metrics**: adds `causal_local_off_evidence_stop` and `causal_completed_unresolved` counters to show that a bounded unresolved cause is a successful completed investigation.

## Safety, accuracy and limitations

No Hubitat devices or rules are modified. All live MCP operations remain read-only and retain their existing capability/confirmation gates. An empty `command-off` page is a bounded observation, not proof of no external or Hubitat-initiated action. Empty app logs are not proof that the app did not execute. Nearby sensor events (before OR after OFF) are timing correlations; claiming a specific Aqara, Hue, Hubitat or other OFF automation still requires compatible app-command provenance or its own historical execution trace.

Regressions cover the exact “possible external causes” wording, synonyms, missing source obligations, no cross-room expansion from an exact local OFF correlation, inconsistent mixed ON/OFF tables, unsupported OFF-only certainty and categorical exclusion paragraphs, final API output and one-provider-round local fixes. Live execution time, tool-call counts and answer quality still require verification after installing 0.17.16.
