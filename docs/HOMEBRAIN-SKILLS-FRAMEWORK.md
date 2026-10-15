# HomeBrain Skills Framework — v0.17.69

## Goals
Make HomeBrain operate Hubitat like a skilled investigator: discover the authoritative tool schema, relate controllers to devices, reconstruct time-aligned command and state history, evaluate anomalies, and make an evidence-ranked diagnosis rather than a generic external-source guess.

## Deployment
Skills ship inside the add-on container at `rootfs/app/skills` and are loaded by `skills_framework.py`. There is no external network dependence to load them. The declared live MCP catalog and hub_get_tool_guide are authoritative for current operations; skills do not grant privileges.

## Runtime flow
1. `select_skills(user_prompt)` chooses operating skill for Hubitat device/rule requests and additionally the investigation skill for causal, history, diagnostic, telemetry and why-requests. Weather/general conversation stays out. Selection is local and does not consume model calls.
2. The orchestrator injects bounded, repo-owned skill instructions when preparing the system prompt. Missing local skill files are ignored, never replaced by an arbitrary path.
3. For a resolved causal subject, `skill_topology.py` constructs a producer-first plan from verified command receipts. It highlights missing app configuration or scoped execution logs and offers live tool hints, while preserving the original user request and read-only constraints.
4. During final causal synthesis, `skill_investigation.py` uses the existing source-typed causal graph and real history receipts to project the exact focal state, preceding command, intervening state boundaries and explicit competing hypotheses. These remain labeled not-proven until acknowledged.
5. `skill_secret_guard.py` redacts common credentials from server-derived messages entering the model and from the final textual answer. The raw execution path and evidence receipts are not modified.

## Evidence and topology semantics
- `command-on` by a Hubitat app verifies command invocation, **not successful Hue/Matter transport delivery**.
- A `switch:on` produced by Matter Hue Bridge Pro verifies the bridge reporting source, not the upstream initiating person/app.
- `triggered[]` identifies subscribers notified after an event, not controllers that initiated it.
- If `switch:off` appears between a relevant command and `switch:on`, preserve it and consider independent bridge input, delayed response and state resync; do not conclude external cause solely on that anomaly.
- Only config returned through a targeted app read is considered *checked*, and current settings do not prove past execution. Empty bounded event/log queries do not prove nothing happened.
- Use source labels, time windows and integrity markers in the final conclusion. Missing historical MQTT/device logs should be reported as gaps, not invented.

## Sources and acknowledgements
Operating principles adapted with attribution from the MIT-licensed Hubitat MCP client skill: https://github.com/kingpanther13/Hubitat-local-MCP-server/tree/main/agent-skill/hubitat-mcp . Refer to upstream `hub_get_tool_guide` for current schemas, capabilities, permission gates and backup requirements. HomeBrain's evidence-planning algorithms are local implementations, not a copy of the upstream rule engine.

## Test matrix
- Light command recorded then bridge report: leading internal-command candidate, not external certainty.
- Intervening OFF then ON: preserve signed timing and anomaly.
- Sensor/button nearby without configured control link: never infer trigger.
- MQTT/mesh health: cached health versus physical packet age and scoped logs.
- Native rule/app diagnostics: settings versus execution; respect missing historical source.
- Credential-containing app config: no secrets in model-facing context or final answers.
- Simple command/weather: no unneeded investigator model context.

## Acceptance
After upgrading the add-on, repeat the 14 October Livingroom Light 1 19:55 investigation (read-only), and Bedroom 3 Mesh 24-hour diagnosis. Inspect the output evidence, current version and request metrics. A GitHub CI pass does not itself prove the locally installed add-on uses this build.
