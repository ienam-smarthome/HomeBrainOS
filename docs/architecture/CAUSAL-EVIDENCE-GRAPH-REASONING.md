# Causal evidence reasoning — normalized graph contract

## Motivation

A command producer and an automation's upstream trigger are different causal edges. HomeBrain previously combined its broad timeline, log receipt summaries, configuration excerpts and a freeform model decision, then attempted to repair unsupported output text. The 0.17.10 Bathroom Light 1 result showed another systemic problem: a later OFF event was assigned to the automation because it followed a sensor's inactive event by 164 ms, despite no directly verified OFF command.

The **shared causal graph** is a bounded, pure normalization step between live MCP reads and language-model reasoning. It is not a replacement for general MCP discovery, rule semantics, history integrity or write authorization.

## Evidence roles

| Relation | Source | Strength | What it cannot prove |
| --- | --- | --- | --- |
| Device state ON/OFF | Device event-history switch boundary | Observed | Who sent a command or whether every historic event is retained |
| App issued setLevel/on/off | Compatible command history with `producedBy` | Confirmed direct producer when unique | Upstream human/manual input or rule's internal conditions |
| Sensor was active before command | Device event history + aligned correlation receipt | Strong correlation if sensor is configured and precedes command | That motion necessarily triggered that particular code branch |
| App's handler was notified | Event `triggered[]` app ID and handler | Observed listener notification | Handler evaluation and effects |
| App configured with motion/mode/timers | Bounded app configuration excerpts | Confirmed **current** configuration | That the same settings were in effect historically |
| App execution logs checked | Timestamp-scoped `hub_get_logs` success and row count | Checked source, possibly zero rows | Unlogged internal conditions or absence of execution |
| Nearby mode changes | Bounded Hubitat location-event history | Observed mode context | That an earlier mode setting could not affect automation conditions |
| Sensor inactive just before OFF | Timestamp-aligned sensor and state histories | End correlation only | The OFF command issuer or timer's execution |

## The graph's control-flow contract

1. Resolve the user's single exact clock time against one observed device state boundary. If the requested time is ambiguous or has no known boundary, do not invent a focal event and do not enter the automatic graph-sufficiency path.
2. Gather the already-required focused command/app/log/sensor evidence. Store bounded actual sensor event samples near the requested start and end edges, including any `triggered[]` handler references.
3. Normalize facts into `build_causal_evidence_graph(evidence, question)`. The graph carries source roles, app ID, timestamp order, evidence completeness, `offAttribution`, and explicit causal limits.
4. If the user specifically asks for alternative causes and current config mentions mode changes, perform one location-history check **only when a live read gateway is available**. Log the attempt and preserve its results; no device write or speculative fan-out is authorized.
5. **Only** for explicit, comprehensive deep questions with confirmed app-command provenance, a configured aligned sensor, checked app config and scoped logs, and no outstanding required mode check, skip model tool-planning rounds and run the shared final evidence-scoped synthesis once. A partially answered request continues using model-directed MCP discovery.
6. Always pass a compact graph into final synthesis for a unique single-event causal question. Do not let later language generation upgrade a lower-confidence edge to “proven execution.”
7. Safe locally corrected wording from shared factual guards can be returned without an extra provider rewrite when the graph is complete and all issues belong to a strict allowlist of local, testable repairs.

## What remains

The graph is deliberately bounded and currently normalizes one switch/dimmer transition; it should eventually accept a general typed event domain and full provenance DAG for Rule Machine actions, manual controls, delays and cancelable jobs. Add dynamic objective-to-tool planning for other investigations and confidence evaluation against a fixed multi-domain test corpus. Compare Claude and HomeBrain with the **same** installed MCP access, timestamps and read-only permissions.

Do not use an OFF-state change or the sensor's later inactivity as direct evidence of the OFF command producer unless a separate compatible command receipt exists. Do not infer the historical rule branch from current configuration. A single successful negative log read is evidence that a bounded window was checked, not a proof that the app did not execute.
