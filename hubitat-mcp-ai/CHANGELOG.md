# Hubitat MCP AI changelog

## 0.10.6

- Makes the AI question guide a terminal system route outside every model-driven
  wrapper, so `What can Ollama help with?` returns immediately.
- Prevents the local planner timeout and unified-agent error previously caused by
  sending this static help request through `qwen3.5:4b`.
- Adds regression coverage proving the unified agent and MCP are not called.

## 0.10.5

- Keeps device-health questions on the authoritative deterministic route so Cloud
  AI cannot reinterpret quiet event timestamps as stale-device faults.
- Routes the Attention shortcut to the deterministic attention collector instead
  of treating `devices that need attention` as a literal device name.
- Installs health and attention routing outside all AI wrappers, preserving live
  Hubitat classifications as the terminal answer.

## 0.10.4

- Pages detailed device-health inventory reads with bounded `limit` and `offset`
  requests, then aggregates every page before classifying devices.
- Detects oversized, truncated, repeated and safety-limited pagination results and
  reports the health scan as incomplete instead of returning a false all-clear.
- Adds regression coverage for the exact oversized MCP response, multi-page
  inventories and MCP servers that ignore pagination offsets.

## 0.8.1

- Fixes the `Suggest one useful automation for the devices I have` Smart Shortcut being intercepted by the universal AI Evidence Planner.
- Gives the existing capability-aware AutomationRecommendationService precedence over the generic read-only fallback for automation suggestion requests.
- Deterministically inspects selected-device rooms, groups and capabilities before choosing one grounded automation candidate.
- Uses Ollama only to improve the wording of the verified candidate; it does not invent devices, capabilities or an existing rule.
- Preserves the Hybrid Assistant universal AI fallback for ordinary analytical questions and keeps clear device controls on their fast verified route.
- Adds regression coverage proving the exact shortcut reaches the specialist skill while normal electricity and home-analysis questions still reach the AI Evidence Planner.

## 0.8.0

- Replaces Control Focus as the default with **Hybrid Assistant mode**: proven controls and verified reads stay fast, while every other connected-home question falls through to the AI Evidence Planner.
- Prevents read verbs such as `show`, `list`, `what`, `why`, `how`, `check` and `tell me` from being mistaken for device-control targets.
- Keeps clear commands such as `Turn on Bedroom 1 Light` and `Set Livingroom Light 1 to 30%` deterministic, AI-free and verified through Hubitat MCP.
- Adds `hybrid_assistant_mode_enabled`, enabled by default, which overrides saved legacy Focus settings during upgrade so existing installations do not remain unintentionally restricted.
- Retains Control Focus only as an optional restricted/troubleshooting mode when Hybrid Assistant is explicitly disabled.
- Moves the current-power summary outside Control Focus so it remains a fast verified read in normal assistant mode.
- Adds a grouped Octopus whole-house energy reader for Power, Today, Yesterday, Week, Month, rates and standing charge display sensors.
- Routes requests such as `Total power consumption today` to the matching Octopus period display instead of returning a scope card.
- Routes `Show octopus live meter display` to the complete Octopus display family instead of fuzzy-searching for one exact device.
- Keeps all AI planning read-only and evidence-bound; Python remains authoritative for MCP calls, calculations, commands, confirmations and final-state verification.

## 0.7.2

- Fixes `Show power consumption` failing after live MCP reads with `AttributeError: 'str' object has no attribute 'get'`.
- Stops the Control Focus formatter from treating the serialized `technical` debug field as structured evidence.
- Reads individual and whole-home Power Meter rows directly from the authoritative `measurement_readings` collection.
- Keeps whole-home aggregate values separate from the individual-device total and preserves the active/idle breakdown.
- Adds a production-shaped regression where `technical` is a string, proving the formatter cannot call mapping methods on debug text.

## 0.7.1

- Introduces **Control Focus mode**, enabled by default, to keep HomeBrain centred on reliable device control and authoritative live device reads.
- Preserves natural and exact controls, confirmation replies, device health, metric rankings, inventories, weather and other proven deterministic shortcuts.
- Disables broad AI Evidence Planner routing while Control Focus is enabled, preventing overlapping general-assistant routes from misclassifying simple device questions.
- Adds a dedicated deterministic current-power summary for phrases such as `Show power consumption`, `Show current power usage` and `List power readings`.
- Reads fresh selected-device Power Meter values, ranks active devices, totals individual measured draw and separates 0 W / idle readings without using an AI model.
- Returns a clear Control Focus scope card for broad analysis questions rather than fuzzy-searching for a device or falling into an unsupported Ollama error.
- Keeps the full AI Evidence Planner available as an opt-in mode by disabling `control_focus_mode_enabled` in add-on Configuration.
- Adds `control_focus_mode_enabled` and `control_focus_allow_verified_reads`, both enabled by default.

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
