# Hubitat MCP AI changelog

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
