# HomeBrain 0.17.11 — Shared causal evidence graph and bounded deep-reasoning optimization

The 0.17.10 live investigation of Bathroom Light 1 at 07:53:36 correctly attributed the ON command to App 4013 and identified configured LWR01 motion as the leading upstream trigger, but its model needed six reasoning rounds and fifteen tool calls. The answer inferred that App 4013 managed the later OFF event because sensor motion went inactive 164 milliseconds earlier, even though **the returned evidence did not establish the OFF command's producer**.

## New architectural foundation

- **Source-tagged causal graph:** A reusable module `causal_evidence_graph.py` normalizes one observed state interval into confirmed direct commands, configured upstream sensors, actual sensor events, app-handler notifications, current app configuration, scoped execution logs, mode history, and observed OFF transitions. Each relationship preserves its epistemic class (confirmed, configured, temporal correlation, listener notification, or unresolved).
- **Evidence direction:** A configured sensor's motion event before a command strengthens the initiating-trigger hypothesis but is not an internal rule-execution trace. `triggered[]` proves event delivery to an app handler, not that its conditions passed. App command provenance proves the direct actuator command, not manual/input absence upstream. An inactive sensor event before OFF is time correlation, not proof the same app issued an OFF command.
- **No double-reading sensor history:** The host now retains a small, relevant set of sensor events near both interval boundaries and their `triggered[]` handler metadata. Previously it only recorded “read available,” prompting the model to repeat the MCP operation to recover already-collected facts.
- **Dynamic investigation sufficiency:** For an explicitly multi-part deep request, the graph checks whether the controlling command, candidate sensor, configuration and event-time app logs are actually examined. If the app configuration references mode and the user requests alternatives, the host performs **one bounded, read-only location/mode history check**, if that live MCP gateway is available. When every requested class is covered, HomeBrain proceeds directly to one evidence-scoped model synthesis instead of repeatedly requesting the same facts in exploratory rounds. Missing, ambiguous, nonconfigured or unavailable sources retain the existing model-driven MCP discovery loop.
- **Final synthesis:** The same graph is included in the final model evidence packet for all supported single-event causal requests. It explicitly cautions against unsupported OFF attribution and internal-branch claims.
- **Repair efficiency:** When a complete graph exists and every synthesis-validator issue is already fixed by safe localized deterministic guards, HomeBrain keeps the corrected answer rather than asking the model to rewrite the same facts again.
- **Metrics:** `causal_graph_sufficient` and `causal_graph_mode_reads` record when the optimized path was used. Existing read/write safety, MCP server permissions, confirmation and sensitive-command checks are unchanged.

## Tests

Synthetic integration tests cover real-style ON and OFF timestamps, direct app command versus OFF provenance, configured motion and `motionHandler` event delivery, successful zero-entry scoped app logs, a nearby earlier mode, later/inverted sensor events, ambiguous event times, raw sensor event selection, and single-pass final synthesis after host evidence has been collected. No live Hubitat devices or rules were modified.

## Boundaries

This v1 graph applies to a **single uniquely identifiable binary device event**, with direct command semantics currently grounded in Hubitat's switch/dimmer command records. Ambiguous multi-day histories do not silently collapse into a single cause. The graph is not a self-acting agent or proof of the internal execution branch. Other MCP capabilities remain dynamically available through existing discovery and permission gates.

The six-round/29.8-second example motivates the improvement, but actual reduction depends on the installed MCP server, provider behavior, returned evidence and user question. Compare a new live trace before claiming a specific performance gain.
