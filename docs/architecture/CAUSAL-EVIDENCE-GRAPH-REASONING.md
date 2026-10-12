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

## v0.17.12: externally reported physical events and downstream responses

A bridge-reported `switch=on` and a Hubitat app-issued `setLevel` are separate causal events. For a named unique HH:MM (with optional date), focal selection outranks earlier long intervals; ambiguity still fails closed.

The generic graph includes these additional fact classes:

| Graph field | Grounded source | Meaning and limits |
| --- | --- | --- |
| `physicalStateBoundary` | switch-state event `type`, `producedBy`, `triggered[]` | Hue/Aqara/Matter bridge may be the reporting origin; apps in `triggered[]` are listeners, not necessarily initiators |
| `controllerCandidate` | Bounded controller history and aligned light boundaries | Signed delta and repeated pairing; a recorded button report **after** ON cannot be claimed as an earlier Hubitat command |
| `postOnCommands` | Targeted `command-setLevel` history for the subject | Later level changes with precise ordering and actual app producer; not the original ON cause |
| `reactiveApp` | One relevant notified light-switch handler, current app config and scoped logs | Evidence the app could react to external ON; current settings and a zero-row log search cannot prove execution history |
| `offSensorCorrelations` | Correlated inactive occupancy events near OFF | Relevant pattern only; never uniquely attributes OFF to Aqara, Hue, Hubitat or an unidentified controller |

For deep physical-source investigations, HomeBrain checks a bounded post-ON command page and the relevant subscribed lighting app’s configuration/logs without issuing device commands. The graph-complete fast path requires the reported physical boundary, multiple aligned controller events, actual reviewed sensor evidence, command-setLevel history, app configuration, event-time logs, and mode history if configured and requested. Otherwise general MCP discovery remains available.

A Hue-native controller mapping or Aqara external automation history is outside the Hubitat MCP read surface. Even when three button/ON pairs are within ~150 ms, the relationship is a strongly supported hypothesis, not a verified native binding. Likewise, the app’s brightness adjustment after ON is observable without inferring the exact code branch unless app source or execution logs support it.
