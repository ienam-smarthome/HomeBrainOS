# v0.18.241 — consolidate Investigation V2 evidence into original HomeBrain

## Decision

The original HomeBrain MCP agent remains the primary assistant. V2 is frozen as a separate **experimental read-only regression harness**; no parallel V2 final-answer engine or JSON claim-publisher is invoked by this release's original agent. The V2 source-attested event projection and bounded timeline evidence utilities are reused inside the original answer coordinator, allowing its existing model to write concise natural-language answers.

## Why this release

The 30 October Bathroom Light 1/2 and Shower Light live comparison revealed a split failure. V2 had relevant motion/occupancy event evidence yet published a timeline-only fallback because structured JSON synthesis was rejected. The original HomeBrain produced a fluent account but claimed an automation *activated* a light even when the light's ON state was reported **before** that app's brightness adjustment. Successful recent log reads also did not necessarily cover the requested incident.

## Implementation

- New `unified_investigation_bridge.py` converts only successful, read-only, independently ID-scoped original MCP event receipts into the same source-attested V2 evidence projections. It verifies original target device identity and user-question relevance; user text and free-form model names cannot manufacture target IDs.
- Build temporal relationships for the original AI: issued command **before** source-reported state, subsequent `setLevel` **after** an already ON state, independently read sensor edge within 3 seconds of ON, and observed Hubitat mode changes. The source packet includes precise timestamps, actor IDs, target labels, and explicit boundaries on causal certainty.
- Original `FinalAnswerCoordinator` uses these relationships as **advisory evidence** in the existing one-pass, natural-language, tool-disabled final synthesis, retaining original factual validators, guarded tool choices and full evidence receipts. It is not required to return V2 structured JSON, and it does not select a V2 host-authored answer.
- Original `mcp_agent_orchestrator` gets one model-selected read-only continuation **only when** two verified named target histories contain ON transitions without a preceding attested ON command and no independent input sensor event history was read. The model, not this module, chooses the next live-advertised read. No tool permissions change; no writes.
- Historical `hub_get_logs` query success is reported separately from **actual incident log-time coverage**, which remains unverified absent direct timestamped log evidence. A later 10:00 log cannot prove a 02:00–07:30 event.

## Safety limits

Neither the reporting Hue Bridge nor `triggered` app listeners establish the initiating controller. Temporal sensor correlation is not an internal Home Assistant/SmartThings/Hue automation trace. A `setLevel` issued 46 ms *after* reported ON is a reaction/brightness adjustment, not source proof of the earlier ON. Device state is source-reported, not a physical acknowledgement. V2's experimental API remains available for regression comparison, but is not the recommended end-user investigation path.

## Release test requirements

Replay the real-case 46 ms brightness-after-ON, 252 ms occupancy lead, 89 ms Shower MS605 lead, button 4 preceding OFF, School Run mode and history cutoff; confirm that later sensor edges do not become preceding causes. Test no verified target lookup, untrusted source row, missing independent input, recent-only logs, original final-answer integration, no V2 structured JSON, zero tool escalation, and existing read/write/confirmation suites. Run entire Python suite, release assurance, metadata validation and add-on container smoke. After merge, verify deployed add-on version on Home Assistant and perform live tests; no CI result can confirm actual external control provenance.
