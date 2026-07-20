# Hubitat MCP AI changelog

## 0.7.0

- Introduces **AI Evidence Planner**, moving broader home analysis from one fixed route per question to AI-selected, evidence-bound read planning.
- Lets AI choose only from an approved read-only catalogue: live home snapshot, device health, numeric measurements, hub health, selected-device inventory, targeted recent events, weather and today's calculated light usage.
- Keeps Python authoritative for every MCP request, device label/ID lookup, calculation, coverage check, safety boundary and all write paths.
- Supports at most two evidence rounds: an initial plan and one optional bounded follow-up when the first package is genuinely insufficient.
- Uses Direct Ollama Cloud first by default, with local Ollama retry and deterministic evidence fallback when AI is unavailable.
- Gives planning and synthesis models no command tools, arbitrary MCP tool names or authority to claim that a device changed.
- Preserves exact controls, device health, live metric rankings and other proven MCP-fast routes instead of adding AI latency to clear requests.
- Extends broad planning to natural electricity, bathroom, ventilation, room, appliance and environmental questions.
- Adds independent settings for planner enablement, Cloud preference, evidence-round limit, planning/synthesis timeouts and inventory size.
- Adds regression coverage for whitelist enforcement, Direct Cloud planning, second-round evidence, deterministic fallback and strict control-route isolation.

## 0.6.5

- Adds a dedicated **whole-home priority insight** route for questions such as `What are the three most important issues at home right now?`, `What looks unusual at home?` and `What needs attention at home?`.
- Installs the route after the broad semantic-read pipeline so words such as `most` and `important` can no longer misroute a whole-home diagnostic request into metric comparison.
- Gathers a truthful live Hubitat snapshot before any AI call, including explicit health alerts, offline states, low batteries, alarms and open contacts.
- Uses Direct/Hybrid Ollama only to rank and phrase the already-confirmed issue rows; the model receives no MCP tools and cannot invent device states.
- Honours requested counts from one to five and refuses to invent extra problems when fewer confirmed issues exist.
- Returns the same ranked evidence deterministically when Direct Cloud is unavailable instead of falling through to the unsupported natural-agent error.
- Reports a dedicated `home-insight` trace and the actual provider, including `Ollama Cloud Direct` when the Windows PC is off.
- Adds regression coverage for the exact reported question, Direct Cloud synthesis, deterministic Cloud failure fallback and late-route installation order.

## 0.6.4

- Fixes semantic-read questions failing with `qwen3.5:4b ... All connection attempts failed` when the Windows Ollama PC is offline.
- Gives the structured semantic-intent classifier a bounded model chain: local Qwen first, then the configured Ollama Cloud model through the direct Home Assistant transport.
- Limits the local semantic attempt to 2.5 seconds so an unreachable PC cannot consume the entire request window before Direct Cloud is tried.
- Keeps deterministic parsing as the final interpretation fallback and continues using deterministic MCP code for all live values, rankings and calculations.
- Prevents successfully Cloud-classified semantic reads from falling through to the unrelated natural-agent fallback.
- Reports the actual classifier provider, including `Ollama Cloud Direct`, rather than labelling every semantic intent as Local Ollama.
- Adds `semantic_intent_cloud_fallback_enabled` and `semantic_intent_cloud_timeout_seconds`, enabled with a 12-second default.
- Adds regression coverage for PC-offline Direct Cloud classification and the normal PC-online local path.

## 0.6.3

- Adds **PC-independent direct Ollama Cloud access** from the Home Assistant add-on using `https://ollama.com/api` and a password-protected API key setting.
- Routes configured Cloud-model requests directly from Home Assistant while keeping local Qwen requests on the LAN Ollama PC.
- Uses failover order: Direct Ollama Cloud, signed-in local Ollama Cloud proxy, then the existing local Qwen fallback and deterministic Hubitat output.
- Converts local proxy tags such as `gemma4:31b-cloud` to direct API model names such as `gemma4:31b`, with an explicit model override option.
- Combines local and direct `/api/tags` results so Cloud remains available to HomeBrain model selection when the Windows PC is switched off.
- Adds separate Local Ollama and Direct Cloud diagnostics, including API-key configured state and the last selected transport, without exposing the secret.
- Adds `ollama_direct_cloud_enabled`, `ollama_direct_cloud_base_url`, `ollama_direct_cloud_api_key`, `ollama_direct_cloud_model` and `ollama_direct_cloud_fallback_local_proxy` settings.
- Adds offline-PC, bearer-authentication, model-rewrite, local-isolation and local-proxy-fallback regression tests.

## 0.6.2

- Adds **goal-based AI lighting control** for subjective requests such as `Make Livingroom Light 1 comfortable for watching TV`.
- Sends these requests to the stronger configured Cloud structured-control model first, with the selected-device inventory and no command tools.
- Lets AI translate low-risk lighting goals into a concrete proposed level, using conservative starting points for TV, relaxing, reading, cleaning and bedtime.
- Caps goal-plan confidence below the automatic-execution threshold so HomeBrain always shows the chosen percentage and asks for confirmation before changing the light.
- Keeps Python responsible for device resolution, policy, MCP execution and final-state verification; the model cannot select IDs or claim success.
- Prevents failed subjective controls from falling through to the general natural-answer agent and producing `No authoritative MCP evidence` errors.
- Returns a focused request for an explicit percentage when no configured structured model can produce a safe proposal.
- Adds `control_agent_goal_prefer_cloud`, enabled by default, while preserving local fallback and all exact deterministic fast controls.

## 0.6.1

- Fixes natural controls such as `Put living room one light at about thirty percent` being parsed as the literal device name `living room one light` and then opening a two-device choice menu.
- Decomposes common spoken targets into semantic fields before device matching: room, device type and ordinal.
- Resolves `living room one light` as `Living Room` + `light` + ordinal `1`, and `living room light two` as ordinal `2`.
- Treats numbered-bedroom phrases such as `bedroom one light` as the canonical device `Bedroom 1 Light` in room `Bedroom 1`.
- Keeps these clear controls fully deterministic, avoiding the five-second AI rescue timeout and unnecessary confirmation.
- Preserves Agent-First Control for genuinely ambiguous or unsupported natural language, with models still restricted to structured intent and no command tools.

## 0.6.0

- Introduces **Agent-First Control**, modelled on the successful Claude MCP workflow: understand the natural instruction, inspect the selected-device inventory, build a structured plan, then execute and verify through deterministic Hubitat code.
- Sends probable natural device controls to Control Agent before any routine read-only or general answer route, preventing instructions from receiving unrelated room-only evidence.
- Adds deterministic spoken brightness grammar for phrases such as `Put bedroom one light at about thirty percent`, including number words, approximate wording, half, quarter, three-quarters and full brightness.
- Keeps proven exact on/off and numeric level commands AI-free and preserves their existing fast paths.
- Uses the local planner model first for non-deterministic control interpretation and optionally retries the stronger configured Cloud model when local interpretation times out or fails.
- Gives both interpretation models only the selected-device inventory and strict `ControlIntent` JSON schema—no MCP command tools and no authority to choose device IDs or claim success.
- Keeps Python responsible for selected-device matching, risk policy, all-targets-before-write preflight, MCP execution and final-state verification.
- Labels natural control requests as `control-agent` in request traces instead of misleadingly calling them routine reads or Cloud planner requests.
- Adds `control_agent_cloud_fallback_enabled` and `control_agent_cloud_timeout_seconds` configuration options.

## 0.5.9

- Replaces the dashboard's visible **Switches on** tile with an actionable **Offline / stale** device-health tile.
- Uses the same authoritative detailed `healthStatus` classifier as the `Are any devices offline or stale?` fast route, so dashboard and conversational results stay aligned.
- Displays the combined confirmed issue count, with a subtitle separating offline and stale-telemetry totals.
- Excludes quiet timestamps from the warning count.
- Highlights the tile when one or more confirmed health issues exist and opens the detailed device-health answer when tapped.
- Keeps `switches_on` in `/api/dashboard` for backwards compatibility while no longer presenting it in the web interface.
- Fetches device summary and health metrics concurrently and caches the combined dashboard snapshot using the existing refresh interval.
- Leaves the rest of the dashboard available when the health scan fails, showing the health tile as unavailable instead of breaking all summary cards.

## 0.5.8

- Fixes explicit Hubitat `healthStatus: offline` values being missed when the separate MCP `Health Check` capability query returned no usable rows.
- Reads detailed live states for every selected device and treats `healthStatus` as authoritative, even when the device also reports a benign general `Status` such as `clear`.
- Restores live `currentStates`, detailed attributes and capabilities when the MCP stale filter omits them.
- Correctly reports devices such as Roborock Q7 Max, Tuya button remotes and HealthCheck outlets as offline when their Hubitat device pages show `healthStatus: offline`.
- Keeps `lastActivity` age separate so quiet FP sensors and unchanged switches are not called offline without a negative live health state.
- Removes the dependency on the exact `Health Check` versus `HealthCheck` capability spelling.

## 0.5.7

- Fixes false stale-device warnings caused by treating Hubitat `lastActivity` age as proof that a device is offline or malfunctioning.
- Requires an explicit negative Health Check state such as `offline`, `unavailable`, `failed` or `unreachable` before reporting a device as offline.
- Classifies event-driven or normally static devices—buttons, FP presence sensors, unchanged sockets and switches, cameras, robot vacuums and similar devices—as **quiet timestamps**, not health faults.
- Keeps a separate **stale telemetry** category for periodic climate, power, energy, voltage and similar reporting that has genuinely stopped beyond the configured threshold.
- Lets a positive Health Check state override an old activity timestamp.
- Routes common questions such as `Are any devices offline or stale?` directly to deterministic MCP processing, with no Gemini or local-model wording pass.
- Reports Offline, Stale telemetry and Quiet timestamps as separate metrics and exposes the classification evidence under Technical details.

## 0.5.6

- Fixes exact read-only device controls such as `Turn off FP2 Bedroom 3 Lux` opening a nearby-light choice menu.
- Retains exact selected-device evidence for Lux, illuminance, motion, presence, contact, temperature, humidity and battery sensors while keeping them outside the actuator graph.
- Distinguishes a known non-controllable device from an unknown or misspelt target using exact canonical spoken-name matching only.
- Stops before local AI rescue, fuzzy candidates, confirmation or command execution when the exact selected device does not expose switch or level control.
- Returns a direct explanation such as `FP2 Bedroom 3 Lux is an illuminance (Lux) sensor and cannot be turned off`.
- Records that AI rescue was not attempted and that no substitute actuator was offered or changed.
- Keeps normal fuzzy clarification and AI rescue available for genuinely unknown or malformed targets.

## 0.5.5

- Fixes target-before-action commands such as `Switch the second living-room light off` being sent to the Cloud planner and broad legacy confirmation list.
- Parses postfix `on`/`off` grammar deterministically before any AI call.
- Converts room, device type and ordinal language into structured constraints: `Living Room` + `light` + ordinal `2`.
- Resolves the selected device through the Control Agent graph and executes through the existing verified MCP controller.
- Routes clear postfix controls as MCP-fast requests, with no Cloud model and no unnecessary confirmation.
- Keeps contextual or grouped forms such as `turn the other light off` and `turn all living-room lights off` on the guarded structured interpretation path.
- Supports exact target-before-action forms such as `Switch Bedroom 1 Light off` without changing prefix commands such as `Switch off Bedroom 1 Light`.

## 0.5.4

- Fixes `set Bedroom 1 Light at 30%` being parsed with the fake target name `Bedroom 1 Light at`.
- Separates prepositional (`to`/`at`) and bare absolute-level grammar so prepositions cannot be absorbed into device labels.
- Parses valid absolute level commands directly into one deterministic `set_level` intent before the older compatibility parser runs.
- Rejects targets ending in leftover control syntax such as `at`, `to`, `percent` or another numeric level instead of opening an unrelated device-choice menu.
- Keeps clear exact level instructions AI-free, so a local Ollama timeout cannot delay or block them.
- Adds an end-to-end replay requiring the exact device to resolve, one verified level execution to begin, and no confirmation or AI rescue response.

## 0.5.3

- Adds a one-pass local AI rescue when a deterministic control intent cannot resolve safely against the selected-device graph.
- Keeps exact successful controls AI-free; Qwen is called only after the first structured plan remains unresolved.
- Supplies the failed intent and resolution reasons to the tool-free local interpreter, then accepts the rescued plan only when it resolves more devices or narrows clarification safely.
- Never accepts device IDs from AI, never gives the rescue model MCP tools, and never retries a write automatically.
- Preserves the original safe clarification when the rescued interpretation is unsupported, repeated or no better than the deterministic plan.
- Adds `control_agent_ai_rescue_enabled`, enabled by default, so the rescue pass can be disabled independently.
- Filters the Control Agent graph to actuators with switch/level evidence or clear actuator identity, excluding Lux, illuminance, motion, presence, battery, temperature and humidity sensors from control choices.
- Retains clear actuators whose compact summary temporarily omits state metadata, such as fans and sockets, without allowing sensor-only labels into the graph.
- Keeps the canonical `parameters` plus MCP `waitFor` dimmer execution and combined turn-on-at-level parsing introduced in 0.5.2.

## 0.5.2

- Fixes `setLevel` calls that were accepted by MCP but left the dimmer unchanged because HomeBrain preferred a compatibility key such as `params` over the canonical `parameters` field.
- Sends the MCP Rule Server's authoritative command shape: `parameters: ["30"]` for a 30% level request.
- Uses `hub_call_device_command.waitFor` to block-poll the device's `level` attribute and confirm the resulting value in the same MCP call.
- Returns immediately when server-side convergence succeeds; no separate device-catalogue verification call is required.
- Performs only one independent fresh read after a server-side timeout and never blindly resends the command.
- Keeps bounded local verification for older/custom MCP servers that do not advertise `waitFor`.
- Routes exact absolute level commands as deterministic MCP-fast controls instead of labelling them as Ollama-planner requests.
- Interprets `turn on Bedroom 1 Light to 30%` and `turn Bedroom 1 Light on at 30%` as one deterministic `set_level` action, so the percentage is never included in the device name and no unnecessary device-choice menu is shown.
- Rejects out-of-range level values instead of silently clamping and auto-executing them.

## 0.5.1

- Fixes deterministic `setLevel` commands being reported as failed when the MCP server exposes the Hubitat capability as `SwitchLevel` rather than `Switch Level`.
- Shapes level command parameters from the live `hub_call_device_command` schema, including string-array parameter schemas.
- Verifies dimmer levels from compact `SwitchLevel` current states first, then compatible summary and detailed fallbacks.
- Polls only the first evidence source that exposes a numeric level and uses a dedicated three-second maximum verification window.
- Stops early when the MCP server exposes no level field at all instead of waiting through the seven-second switch-control timeout.
- Keeps exact level commands fully deterministic: no local or Cloud model is invoked, and fresh selected-device preflight remains mandatory.

## 0.5.0

- Introduces **HomeBrain Control Agent v1** for direct device control.
- Keeps exact single-device controls deterministic while using local `qwen3.5:4b` only to produce a strict, tool-free `ControlIntent` for contextual, grouped, ordinal and exclusion-based commands.
- Builds a selected-device graph containing authoritative Hubitat IDs, labels, rooms, inferred device types, ordinals, conservative spoken forms and explicit learned aliases.
- Resolves every requested target before the first write and preflights the complete plan against a fresh selected Switch inventory.
- Applies confidence and risk policy: unique low-risk controls can execute automatically; sensitive devices, large groups and lower-confidence plans require confirmation; unresolved plans send zero commands.
- Reuses the existing cache-bypassed MCP command and final-state verification engine, so AI cannot claim control success.
- Adds structured per-browser references for `it`, `other`, `both` and follow-up commands without asking the model to reconstruct raw chat history.
- Adds explicit persistent aliases, for example `remember "big light" means "My Floor Lamp"`, with `forget alias big light` for removal.
- Adds verified `setLevel` execution with fresh level readback.
- Keeps Cloud outside device-ID selection, command execution and verification.

## Earlier releases

The complete changelog through 0.5.0 is preserved in [CHANGELOG_HISTORY.md](CHANGELOG_HISTORY.md).
