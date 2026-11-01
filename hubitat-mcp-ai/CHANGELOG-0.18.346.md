# Hubitat MCP AI v0.18.346 — recent causal command-source completeness

## Evidence and failure
In the first cross-domain user-run v0.18.345 Livingroom Light 2 investigation, the model identified a controller based on a nearby generic Hubitat log, even though the OFF state report was earlier and **no explicit target-scoped command-off history was queried**. In the returned Technical JSON: missingSourceKinds includes command_history; causalInitiatorVerified=null; evidenceComplete=false. The model's app/command assertion was therefore unsupported. Model latency 31.5s, six rounds, eleven tool calls. Actual acceptance FAILED; no Claude-parity assertion.

## Architecture fix, not a one-device patch
- Extend the existing shared command-source obligation planner to **most recent / latest single-device switch ON/OFF causal requests**, which often omit internal device IDs and dates. Require exactly one verified targeted lookup, same-label source-timed switch observation, an already scoped successful device-event horizon (1–720h), and original question's causal intent.
- When the required command-event history is absent, reuse the already-authorized, read-only `hub_list_device_events(attribute=command-off/on)` pathway, max one attempt per target/action/horizon; no uncontrolled loops or extra Gemma rounds. A successful empty page never proves the absence of a command.
- Model-facing request-local packet and Technical JSON `recentCommandIssuerSource` expose a typed source verdict: verified state boundary, status of command history read, issuer witness only when a positively producer-identified command event exists, timestamp relative to reported state, and explicit lack of physical cause proof. Bridge-produced state and downstream event listeners are not command issuers. A generic app log *after* an OFF report is not an earlier command witness.
- Keep natural model-authored responses, no new canned prose publisher, untouched command permissions and opt-in model-first telemetry mode.

## Tests, limits and next acceptance
- Synthetic anonymous fixtures cover missing source read, strong positive issuer command, post-report command timestamp, wrong-device actor, duplicate failed read, missing identity/observed focal state and noncausal questions.
- The source-verdict packet is factual guidance, not a semantic guarantee. Even an attested command does NOT prove it triggered the observed state, upstream automation input, delivery or physical execution.
- **No live Hubitat/HA changes.** Full CI, release validation and container smoke before merging. Model accuracy effect NOT MEASURED; first user acceptance should target a *different* domain (heating scheduler protection, ventilation fan) rather than rehearse this one event.
