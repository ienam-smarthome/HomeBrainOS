# Hubitat MCP AI changelog

## 0.10.178

### Restore semantic summary registry wiring

- Restores the exact semantic home-summary route to `AnswerGuardRegistry` after
  the startup hotfix accidentally reverted only the public entrypoint wiring.
- Keeps the 0.10.177 startup fix: request composition is finalised before the
  runtime HTTP route bridge is installed directly.
- Preserves exact-summary evidence collection, required-fact validation,
  synthesis fallback and response metadata.
- Adds a regression covering both registry wiring and direct runtime route setup.

## 0.10.177

### Fix runtime route bridge startup

- Finalises the declared `application.ask` composition before rebinding HTTP routes.
- Runs `install_runtime_route_bridge()` as route setup rather than as an ask-layer installer.
- Fixes the startup crash reporting that `runtime-route-bridge` did not wrap `application.ask`.
- Preserves the already composed request handler, cancellable `/api/ask`, runtime version routes and Web UI rebinding.

## 0.10.176

### Migrate exact semantic home summaries into the terminal-route registry

- Moves exact whole-home summary phrases into `AnswerGuardRegistry` as an ordered
  terminal route.
- Preserves verified semantic evidence collection, required-fact validation,
  synthesis fallback and response metadata.
- Keeps unmatched queries and failed evidence collection on the existing
  passthrough path.
- Retains the legacy installer for standalone compatibility.
- Leaves the broader semantic home query route and every other guard unchanged.

## 0.10.175

### Remove the duplicate runtime thermostat wrapper

- Stops the final HTTP route bridge from reinstalling the legacy thermostat
  wrapper outside the declared `AnswerGuardRegistry` stack.
- Keeps the cancellable `/api/ask` route bound to the already composed request
  handler, including the registered thermostat terminal route and summary guard.
- Prevents duplicate thermostat evidence reads and duplicate post-processing.
- Leaves runtime version, Web UI route rebinding and shutdown cancellation unchanged.

## 0.10.174

### Migrate semantic home queries into the terminal-route registry

- Moves broad whole-home summary and attention handling into
  `AnswerGuardRegistry` as an ordered terminal route.
- Preserves semantic classification, verified evidence collection, synthesis and
  category-specific attention filtering.
- Keeps write-like, direct-device and failed-evidence requests on the existing
  passthrough path.
- Retains the legacy installer behind an isolated compatibility adapter.
- Leaves every other guard and terminal route unchanged.

## 0.10.173

### Migrate the hub-health display guard

- Moves Hubitat health display enrichment into `AnswerGuardRegistry` as an
  ordered answer guard.
- Preserves installed firmware, software-update and database-size presentation.
- Keeps non-hub-health answers unchanged and retains the guard's original
  request-stack position before semantic home summary handling.
- Retains the legacy installer for standalone compatibility.
- Leaves all other guards and terminal routes unchanged.

## 0.10.172

### Migrate named-rule status into the terminal-route registry

- Moves exact named Rule Machine status reads into `AnswerGuardRegistry` as an
  ordered terminal route.
- Preserves exact matching, clarification choices, disabled/paused reporting and
  deterministic Hubitat inventory wording.
- Keeps unmatched queries outside the rule inventory read path.
- Retains the legacy installer for standalone compatibility.
- Leaves all other guards, writes and terminal routes unchanged.

## 0.10.171

### Migrate climate extrema into the terminal-route registry

- Moves highest and lowest room temperature and humidity reads into
  `AnswerGuardRegistry` as an ordered terminal route.
- Preserves room filtering, measurement validation, deterministic wording and
  fail-open delegation when live evidence cannot be read.
- Retains the legacy installer for standalone compatibility.
- Leaves all other guards and terminal routes unchanged.

## 0.10.170

### Migrate thermostat summary handling into the registry

- Splits the existing thermostat wrapper into an ordered terminal route for
  direct live reads and an answer guard for summary corrections.
- Installs both steps through `AnswerGuardRegistry` at the wrapper's original
  request-stack position.
- Preserves live `hub_list_devices` and bounded `hub_get_device` evidence reads,
  direct thermostat wording and summary correction metadata.
- Retains the legacy combined installer for standalone compatibility.
- Leaves every other guard and terminal route unchanged.

## 0.10.169

### Migrate the home-summary consistency guard

- Moves legacy home-summary motion verification into `AnswerGuardRegistry`.
- Preserves the guard's original request-stack position before thermostat and
  climate routes.
- Keeps semantic home evidence and attention responses exempt from rewriting.
- Retains the legacy installer for standalone compatibility.
- Leaves all other answer guards and terminal routes unchanged.

## 0.10.168

### Migrate the first answer guard

- Moves execution-contract annotation into the ordered `AnswerGuardRegistry`.
- Preserves the execution-contract response fields and the surrounding request
  wrapper order.
- Keeps the legacy installer available for standalone compatibility while the
  maintained entrypoint uses the registry path.
- Adds focused delegation, metadata and wiring regression tests.
- Leaves every other answer guard and terminal route unchanged.

## 0.10.167

### Add the answer guard registry foundation

- Adds an ordered `AnswerGuardRegistry` primitive for same-tier terminal routes
  and answer guards.
- Publishes one request wrapper while keeping small route and guard functions
  independently testable.
- Preserves deterministic registration order and rejects duplicate names,
  late registration, and untracked `application.ask` mutation.
- Adds focused ordering, delegation, catalogue, and safety regression tests.
- Does not migrate existing guards yet, so runtime routing behaviour is
  unchanged in this release.

## 0.10.166

### Instrument the complete request-layer stack

- Captures every live `application.ask` assignment in a typed runtime registry
  without changing wrapper order or request behavior.
- Records the terminal answering layer, tier and traversal count in request
  performance diagnostics.
- Adds `/api/request-layers` for the ordered live layer catalogue.
- Classifies all 51 raw assignment sites across 38 production modules into
  the documented safety-preserving routing tiers.
- Confirms every request layer shares the indexed MCP state broker rather than
  constructing an independent client.

## 0.10.165

### Scale dashboard power units

- Displays dashboard power below 1,000 watts in W.
- Converts dashboard power at or above 1,000 watts to kW with compact
  precision, so 3,190 W is shown as 3.19 kW.
- Preserves decimal precision for sub-kilowatt monitored-device totals.

## 0.10.164

### Add active-room and power dashboard summaries

- Adds an Active rooms tile driven by authoritative motion activity and
  light-on state, with deduplicated room names.
- Adds a Power tile comparing the whole-house meter with the aggregate of
  actively monitored device readings.
- Keeps room and power data independently fail-open so one unavailable source
  does not suppress the rest of the live dashboard.
- Rebalances the six summary cards for desktop and mobile layouts.
- Adds API, room-classification, fallback and rendered-dashboard regressions.

## 0.10.163

### Complete the final layer consolidations

- Folds capability-catalogue safety and duplicate-aware spoken-name resolution
  into `device_intelligence_catalogue.py`.
- Folds conservative per-session follow-up handling into
  `conversation_context.py`.
- Removes three superseded sibling modules while preserving their behavioral
  coverage through the canonical classes.
- Distinguishes ordinary same-family function composition from subclass
  accretion in `scripts/analyze_clusters.py`.
- Reduces the maintained application from 118 to 115 production modules with
  zero import-graph orphans.
- Updates repository documentation for Hubitat MCP AI as the sole add-on.

## 0.10.162

### Recognize intentional analyzer layers

- Adds a narrow, family-scoped cluster-analysis allowlist for the documented
  `ollama_agent_fast` and `ollama_agent_inference` layers.
- Reports those live sibling layers as intentional instead of suspect.
- Keeps unlisted sibling-only modules suspicious and allowlisted modules with
  broken imports visible as failures.
