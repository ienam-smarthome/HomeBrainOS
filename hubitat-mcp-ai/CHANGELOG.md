# Hubitat MCP AI changelog

## 0.10.50

- Routes reversed update wording such as `software update` and `firmware update` deterministically.
- Recognises natural Hubitat update variants without invoking Ollama.
- Keeps update-status reads and confirmation available when local AI is offline.
- Propagates forced-backup creation through the filename-safe backup workflow layer.

## 0.10.49

- Forces creation and verification of a fresh backup immediately before firmware updates.
- Stops treating a date-like backup filename as sufficient evidence for the admin-write guard.
- Keeps backup creation and firmware update within the same explicit confirmation workflow.

## 0.10.48

- Reads authoritative Hubitat platform-update status before asking for confirmation.
- Shows installed version, available version, and release channel in the confirmation card.
- Suppresses the destructive action when the hub is current or status cannot be verified.

## 0.10.47

- Creates and verifies the required recent hub backup before starting a firmware update.
- Reuses the hardened backup workflow, including acknowledgment and idempotency safeguards.
- Reports preflight policy failures as not started instead of incorrectly saying the request was sent.

## 0.10.46

- Adds session-scoped, expiring confirmation for Hubitat firmware updates.
- Shows explicit Yes and No actions in the Home Assistant UI.
- Prevents AI retries and duplicate submissions from issuing repeated update commands.
- Adds firmware-update safety coverage to the blocking release gate.

## 0.10.45

- Makes blocking CI propagate pytest failures even when output is captured with `tee`.
- Adds a shared test dependency definition with async-test support and a centralized release gate.
- Runs historical test debt as an explicitly non-blocking audit with failure artifacts.
- Reduces Hubitat MCP CPU load by extending static catalogue, capability and metadata cache lifetimes.
- Moderately extends live device, hub-health and dashboard snapshot caches while preserving write invalidation, control verification and manual refresh.
- Canonicalizes device-field ordering in cache keys so equivalent inventory projections share one upstream fetch while stale and capability filters remain isolated.
- Routes room-first plural requests such as `Find hallway devices` and `Show hallway devices` to the exact deterministic room inventory instead of single-device resolution.

## 0.10.44

- Removes obsolete version-specific release workflows and temporary CI trigger files.
- Adds a repository hygiene test that rejects released-version workflow filenames and temporary trigger artifacts.
- Clarifies the independently versioned Hubitat MCP AI and legacy HomeBrain OS add-ons.
- Disables rule writes by default for new installations while preserving explicit opt-in and paused-rule safeguards.

## 0.10.43

- Polishes deterministic sensor responses with natural room-and-metric wording.
- Formats percentages and temperatures without an unnecessary space before the unit.
- Preserves conventional spacing for power, energy and illuminance values.

## 0.10.42

- Fixes named-device power and energy reads by requesting the MCP
  `hub_get_device` detail operation through the supported gateway translation.
- Recognises `currentState` as an attribute value field alongside
  `currentValue`, `value` and `displayValue`.
- Routes natural period-energy wording such as `How much energy did we use
  yesterday?` to the deterministic Octopus reader.

## 0.10.41

- Makes deterministic measurement resolution use both device labels and
  structured Hubitat room metadata.
- Probes at most three matching devices through `hub_read_devices` when compact
  inventory cannot identify which candidate exposes the requested attribute.
- Prefers environmental sensors over obvious actuator-only devices for named
  temperature, humidity and illuminance reads.
- Adds room-based humidity plus named energy and battery regression coverage.

## 0.10.40

- Fixes deterministic named-device reads when `hub_list_devices` returns compact
  inventory rows without room, state or capability metadata.
- Accepts the MCP device ID aliases `id`, `deviceId` and `device_id`, plus the
  label aliases `label`, `displayName`, `name` and `deviceLabel`.
- Covers the real sparse `Freezer (MQTT)` inventory response and verifies the
  subsequent detail read returns its live 77 W power value.

## 0.10.39

- Extends the deterministic named-device reader to temperature, humidity, power,
  energy and battery questions instead of routing those reads through AI synthesis.
- Performs an authoritative `hub_read_devices` detail read for natural questions
  such as "How much power is the freezer using?".
- Prefers devices that expose the requested attribute and leaves aggregate,
  comparison and period questions with the semantic reader.
- Removes the duplicated word in semantic power-comparison responses.

## 0.10.38

- Fixes deterministic sensor reads when Hubitat returns list-shaped current-state
  records containing `name` and `currentValue` fields.
- Adds attribute aliases and preserves valid zero values for live sensor readings.
- Covers the FP2 Bedroom 3 Lux response shape with end-to-end regressions.

## 0.10.26

- Gives the deterministic Control Agent terminal ownership of every device-control
  request, including natural and ordinal wording.
- Prevents the outer unified AI wrapper from intercepting controls and claiming a
  state change after executing only read/search tools.
- Fails closed when a purported successful control contains no executed mutation,
  preserving safe unresolved and clarification responses.
- Adds deterministic prefix ordinal parsing for requests such as
  `Turn off the second hallway light`.

## 0.10.25

- Promotes the existing selected-device control graph into one public
  `EntityResolver` with typed resolution targets, statuses and match traces.
- Rejects unsupported actions before execution or clarification, preventing a
  switch-only device from being selected for a dimmer-level command.
- Adds typed execution results and distinguishes completed, sent, failed and
  uncertain command outcomes without treating delayed state reporting as failure.
- Exposes the consolidated `fast-control`, `fast-read` and `agent` route class
  alongside existing detailed route names for backwards compatibility.

## 0.10.24

- Separates actual lights from sockets, appliances, cameras and other devices
  that share Hubitat's generic `Switch` capability.
- Routes `total lights on time` and `show lights on time for today` directly to
  the deterministic Hubitat event-history calculator instead of AI synthesis.
- Keeps light-on duration scoped to the current local day and selected MCP lights.

## 0.10.22

- Routes `show power` and `show power devices` to the same deterministic current-
  power summary already used by `show device power`.
- Prevents those short read phrases from being treated as literal device names.
- Keeps comparison questions such as highest-power-device requests on their
  separate ranked comparison route.

## 0.10.21

- Accepts normal read prefixes on concise energy-period aliases, including
  `show energy today`, `get energy yesterday` and `display energy this month`.
- Prevents prefixed requests from falling through to generic exact-device lookup.
- Keeps renamed Octopus period sensors on the deterministic live-value route.

## 0.10.20

- Recognises concise period requests such as `energy today`, `energy yesterday`,
  `energy week` and `energy month` as deterministic Octopus meter reads.
- Keeps those aliases outside the unified AI agent so renamed devices such as
  `Octopus Meter Energy Today` return their verified live values.
- Adds regression coverage for the renamed Energy and Current Power labels.

## 0.10.19

- Reads each discovered Octopus meter with `hub_get_device`, translated through
  the device-read gateway when Hubitat MCP is running in consolidated mode.
- Merges authoritative per-device `value` and `valueStr` states into inventory
  rows whose compact `currentStates` are empty.
- Restores live Power, Today, Yesterday, Week, Month and Standing Charge values
  instead of displaying `No live value` when Hubitat has current data.

## 0.10.18

- Removes unsupported Octopus inventory projections that caused Hubitat MCP to
  reject every deterministic read before executing it.
- Uses the complete shared device index as an additional fallback when filtered
  list responses omit selected Octopus meter devices.
- Routes `find octopus` through the same deterministic family reader as
  `find octopus meter`, keeping discovery and live values consistent.

## 0.10.17

- Keeps Octopus meter display queries on a terminal deterministic route outside
  the unified AI agent, matching their existing `mcp-fast` classification.
- Recognises the live Hubitat labels `Octopus Meter Power`, `Octopus Meter Today`
  and related period sensors in addition to their friendly display names.
- Uses detailed and per-device reads before reporting that an Octopus value is
  unavailable, preventing AI from contradicting live Hubitat states such as `173 W`.

## 0.10.16

- Makes clickable device choices self-contained control commands instead of bare numbers,
  allowing the intended command to survive expired or restarted in-memory confirmation state.
- Keeps numbered typed replies compatible with the pending choice workflow.
- Sends the stable browser session ID in both the request body and header.

## 0.10.15

- Makes ambiguous device-choice tiles clickable while preserving numbered and exact-name replies.
- Submits each clicked choice through the existing session-scoped confirmation workflow, so no
  device command is sent until the selected Hubitat device ID is resolved.
- Adds keyboard selection with Enter or Space and visible hover/focus states for choice tiles.

## 0.10.14

- Makes the restart confirmation card an explicit question instead of hiding the
  confirmation instruction behind structured metrics.
- Adds visible `Yes — restart hub` and `No — cancel` buttons while retaining spoken
  or typed Yes/No replies.
- Shows downtime and recent-backup requirements directly in the confirmation card.

## 0.10.13

- Adds a deterministic, session-scoped two-turn workflow for Hubitat hub restart
  requests, keeping both the prompt and subsequent confirmation outside AI routes.
- Sends the hidden `hub_reboot` MCP operation exactly once with `confirm=true` only
  after a separate `Yes`, while `No` cancels without an MCP write.
- Reports rejected and connection-interrupted restart attempts truthfully and never
  retries a destructive request automatically.

## 0.10.12

- Sends pronoun follow-up controls back to the same Control Agent that executed
  the preceding command, eliminating the split context-store path.
- Preserves the complete verified prior control scope so `turn it off`, `switch
  them on`, and `turn it back on` operate on the same device or device group.
- Parses these follow-ups deterministically and returns a safe unresolved response
  without AI guessing or writes when no verified control context exists.

## 0.10.11

- Routes contextual device controls such as `turn it off` and `switch them on`
  through verified per-session Hubitat device IDs instead of AI text history.
- Preserves an immediately preceding verified multi-device control scope, allowing
  `it` to refer naturally to the previously controlled group.
- Prevents successful inventory reads from masking failed writes; HomeBrain now
  reports complete or partial device-control failure instead of claiming success.

## 0.10.10

- Treats a plural room/type target such as `hallway lights` as every matching
  selected light in that room when the live inventory proves a multi-device group.
- Preserves exact plural device aliases and singular requests, so `hallway light`
  still asks which device while a real device named `Christmas Lights` remains one
  exact target.
- Keeps group safety policy intact: sensitive or large groups still require
  confirmation, and every selected Hubitat ID is resolved before the first write.

## 0.10.9

- Adds a deterministic named Rule Machine controller for pause, resume, enable,
  disable, run and stop requests before AI or device routing.
- Resolves exact normalized rule labels and Rule IDs without asking the user to
  choose when the target is unique; partial or duplicate matches never write.
- Maps enable/disable to Rule Machine resume/pause and keeps run versus stop
  semantics distinct, while accurately describing pause-state verification limits.

## 0.10.8

- Installs grounded automation recommendation matching outside every AI wrapper,
  preventing the unified planner from intercepting the recommendation shortcut.
- Preserves the pending recommendation in the browser session so the existing
  review-first `Build rule` workflow continues to work.

## 0.10.7

- Routes combined automation recommendation and rule-writing requests through the
  grounded device-aware recommendation service.
- Keeps rule writes in the existing review-first workflow: recommendation, draft,
  explicit creation confirmation, then a paused Hubitat rule.
- Corrects false `no device list` synthesis after a successful MCP inventory read.

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
