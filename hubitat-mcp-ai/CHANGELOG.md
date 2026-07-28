# Hubitat MCP AI changelog

## 0.10.196

### Canonicalize the large live module owners

- Renames the Hubitat Rule Machine and guarded recovery modules to canonical
  capability names while preserving the complete safety inheritance order.
- Retires the remaining `_safe` and `_v2` production filenames for power,
  system and weather presentation without compatibility shims.
- Removes three tracked source backup copies; Git history remains the recovery
  source for superseded implementations.
- Adds repository checks that prevent new patch/version-suffixed production
  modules and tracked `.backup` copies.
- Prevents a selected device named `Battery` from making ordinary low-battery
  prose fail the AI grounding guard.
- Includes verified non-light devices that are on in whole-home semantic
  summaries so active appliances are no longer hidden from synthesis.
- Adds an optional Google Gemini reasoning provider for evidence planning,
  grounded summaries and unified open-ended answer synthesis.
- Keeps MCP tool execution and controls local, redacts the Gemini API key, and
  falls back through Ollama Cloud and local Ollama on quota or transport errors.
- Stops an MCP `available: false` result with no release-channel metadata from
  claiming the hub is fully up to date; beta/preview availability is now
  explicitly qualified against the Hubitat admin UI.

## 0.10.195

### Repair MCP invalidation and add grounded routing safeguards

- Fixes the indexed state broker's stale invalidation override so uncached MCP
  reads no longer fail after the safety-aware base signature receives arguments.
- Rejects AI device claims absent from their supplied MCP evidence, falls back
  to verified structured evidence, and exposes grounding trigger-rate metrics.
- Adds a four-tier catalogue arbiter in passive shadow mode and records the
  winning router, intent, agent, capability and confidence for every final answer.

## 0.10.194

### Route natural log-purpose queries to Hubitat logs

- Keeps natural log requests such as `Check logs to see if there are any
  issues` on the authoritative 24-hour `hub_get_logs` route instead of the
  household device-attention scan.
- Supports equivalent `check whether`, `find`, and `and see` purpose clauses
  for issues, errors, and warnings.
- Preserves the separate bounded request-trace route for explicit HomeBrain,
  assistant, and request diagnostics.

## 0.10.193

### Catalogue live routes and centralize MCP safety metadata

- Expands the passive route catalogue with structured capability IDs, required
  MCP tools, slot schemas, safety classes and runtime route/intent aliases.
- Measures shadow agreement only for comparable runtime identifiers and reports
  unmapped capabilities separately instead of counting false disagreements.
- Preserves MCP output schemas and annotation hints, and reports read, mutate
  and destructive coverage for both visible and gateway-contained tools.
- Centralizes conservative destructive-call confirmation for AI tool execution.
- Invalidates cached state after every recognized mutation family, including
  direct gateway calls.

## 0.10.192

### Query a real 24-hour hub-log issue window

- Requests warning and error logs separately from `hub_get_logs` using
  server-side level filters, a 24-hour window and the maximum 500-row limit.
- Avoids filtering only the default latest 100 INFO/DEBUG-heavy entries, which
  could cover only seconds of activity and falsely report no issues.
- Deduplicates returned rows and groups recurring warnings/errors by Hubitat
  app or device source.
- Reports error, warning and affected-source counts with representative latest
  messages and timestamps.

## 0.10.191

### Read actual Hubitat logs for log queries

- Routes bare requests such as `Check logs for any issues` to the read-only
  `hub_get_logs` diagnostic tool instead of semantic household attention.
- Keeps explicit HomeBrain request-diagnostics wording on its separate bounded
  request-trace route.
- Returns only warning/error/fatal rows when the request asks for issues.
- Exposes device-health classifications as first-class structured rows so
  semantic attention reconciliation cannot lose confirmed offline devices when
  technical debug output is truncated.

## 0.10.190

### Keep ambiguous log requests in the household-health domain

- Requires an explicit `HomeBrain`, `assistant`, or `request` qualifier before
  the bounded request-diagnostics route can intercept a log query.
- Leaves bare requests such as `Check logs for any issues` available to the
  semantic household-attention route.
- Preserves explicit self-diagnostics requests such as `Check HomeBrain request
  diagnostics`.

## 0.10.189

### Observe route overlap without changing dispatch

- Activates the existing `RouteRegistry` as a passive production shadow observer.
- Records every query's complete catalogue match set, selected catalogue route and actual answering route.
- Calculates overlap and registry-versus-runtime disagreement rates in a bounded in-memory report.
- Exposes `/api/route-shadow` for Phase 0 evidence gathering.
- Leaves the maintained request stack fully authoritative; the observer never dispatches or modifies answers.

## 0.10.188

### Route diagnostics explicitly and preserve structured health classification

- Routes HomeBrain diagnostics questions to the bounded request-trace evidence domain instead of treating them as generic household attention requests.
- States clearly when Home Assistant Supervisor and add-on log files were not inspected.
- Preserves the authoritative `offline`, `stale` and `quiet` device-health kind end-to-end instead of reconstructing it from rendered phrases.
- Prevents `Quiet, not offline` from being negation-blindly relabelled as offline.
- Deduplicates health evidence by device ID, falling back to a normalized label only when an ID is unavailable.
- Keeps quiet event-age rows out of fault counts and assigns danger/warning tones only to explicit offline/stale kinds.
- Verifies final offline and stale counts against the authoritative structured health rows.

## 0.10.187

### Fix serialized power-summary diagnostics crash

- Decodes serialized `safe_debug()` technical diagnostics before the shared current-power summary reads idle values and fallback metadata.
- Accepts both dictionary and JSON-string diagnostic payloads.
- Handles malformed or missing diagnostic payloads without raising an exception.
- Adds runtime-shaped regression coverage for the live `show power devices` path.

## 0.10.186

### Share monitored-power discovery across dashboard and direct reads

- Makes `show power devices` use the same bounded inventory and `hub_get_device`
  fallback as whole-house power accounting.
- Keeps genuine 0 W readings as idle while leaving missing power attributes absent.
- Aligns the dashboard monitored-power tile and direct current-power summary with
  the existing deterministic accounting source.
- Repairs the historical `OctopusEnergySummary` public export by aliasing it to the
  maintained `OctopusLiveMeterSummary` class.
- Adds diagnostics showing whether shared targeted discovery was used.

## 0.10.185

### Discover monitored power devices from sparse inventories

- Expands the targeted fallback used when detailed Hubitat inventory projections
  return no usable device rows.
- Ranks explicit power-meter capabilities first, then metering plugs, MQTT/Tasmota
  devices and likely monitored appliances.
- Excludes virtual network-block switches and common sensor-only devices from the
  bounded detail probe set.
- Reports selected candidate labels, scores and the number of numeric power
  readings found for easier live diagnosis.
- Keeps missing readings distinct from genuine 0 W idle readings.

## 0.10.184

### Answer active-room dashboard questions deterministically

- Adds a direct read-only terminal route for questions such as “Which rooms are
  active based on motion or lights?”
- Answers from the authoritative cached dashboard snapshot instead of invoking
  the unified Ollama planner.
- Preserves the current active-room names and details already shown by the live
  dashboard while avoiding the 25-second local-model timeout path.
- Keeps unrelated room, device and control questions on their existing routes.

## 0.10.183

### Migrate final deterministic read routes into the shared registry

- Registers device-health, attention and whole-home priority reads in the existing
  read/execution registry.
- Registers grouped Octopus whole-house energy reads in the same registry.
- Removes the two remaining direct deterministic read wrappers from
  `entrypoint_core.py` while retaining compatibility installers for standalone
  consumers and historical tests.
- Keeps query-classification metadata hooks separate from answer routing.
- Reduces the maintained live request stack by two wrappers without changing
  deterministic route behavior.

## 0.10.182

### Complete the final request-layer registry audit

- Adds an executable audit for the maintained four-registry request composition.
- Verifies migrated legacy answer-guard and terminal-route installers are not
  reinstalled by `entrypoint.py` or `entrypoint_core.py`.
- Verifies request composition is finalised before direct runtime HTTP route setup.
- Marks request-routing Thread 1 step 3 complete when the audit and existing CI
  suite are green.
- Leaves the optional planner redesign deferred and identifies Device Health
  Monitor state bloat as the next independent workstream.

## 0.10.181

### Consolidate read routes with execution guard

- Registers named Rule Machine status reads, climate extrema reads and the
  execution-contract answer guard in one ordered `AnswerGuardRegistry`.
- Preserves named-rule-first and climate-second terminal routing followed by
  execution-contract annotation.
- Removes one redundant request wrapper without changing any route or guard.
- Keeps runtime HTTP route rebinding outside request composition.

## 0.10.180

### Consolidate summary and thermostat guards

- Registers the thermostat live-state terminal route, home-summary consistency
  guard and thermostat-summary guard in one ordered `AnswerGuardRegistry`.
- Preserves thermostat-first routing followed by home-summary consistency and
  thermostat-summary post-processing.
- Removes one redundant request wrapper without changing any route or guard.
- Keeps the consolidated registry between semantic-home handling and the
  read-only terminal-route registry.

## 0.10.179
