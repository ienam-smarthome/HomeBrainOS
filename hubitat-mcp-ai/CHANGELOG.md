## 0.10.146

### Complete Ollama compatibility cleanup

- Removes six production-orphaned Ollama compatibility modules.
- Redirects historical regression tests to the live consolidated class owners.
- Restores the intended static and class-method bindings for unified-agent
  evidence, routing and final-answer helpers.
- Updates repository validation and architecture documentation for the
  maintained four-layer Ollama chain.

## 0.10.145

### Runtime safety-prompt refresh

- Clarifies that gateway routing never relaxes MCP safety checks.
- Distinguishes hub shutdown from reboot and documents the manual power-cycle
  requirement.
- Adds safe physical and virtual-device deletion guidance.
- Documents the rule-engine loop guard and advisory-only tool annotations.
- Requires live tool-guide lookup before writing rule JSON.

## 0.10.144

### App command verification integration

- Routes deterministic app enable/disable verification through the central
  `StateVerification` service.
- Preserves write-response-first and inventory-readback-second behavior.
- Adds regressions for write-confirmed, readback-confirmed and accepted-only
  outcomes.

## 0.10.143

### Central command verification service

- Adds one typed `StateVerification` result backed by the canonical
  `VerificationOutcome` enum.
- Centralises nested field extraction and boolean-state coercion.
- Defines a write-response-first, independent-readback-second verification
  policy.
- Adds focused regressions for verified, accepted, conflicting and failed
  command outcomes.

## 0.10.142

### Remove redundant Rule Machine matcher

- Removes the legacy `named_rule_match_guard` from runtime composition.
- Keeps the central `NamedEntityResolver` as the sole app and Rule Machine candidate-ranking layer.
- Preserves exact-ID confirmation, safe shortened-name clarification and the separate disable guard.
- Adds composition-order regression coverage so the redundant matcher cannot be reintroduced accidentally.

## 0.10.141

### Central named entity resolution

- Adds one typed resolver for Hubitat apps and Rule Machine rules.
- Resolves authoritative IDs and exact normalised names deterministically.
- Keeps shortened names as clarification candidates rather than automatic write targets.
- Rejects unsafe broad one-word fuzzy matches.
- Consolidates execution metadata onto the canonical assistant contracts.
- Adds regression coverage for exact IDs, shortened names, accepted commands and verified commands.

## 0.10.140

### HomeBrainOS 2.0 execution contracts

- Defines the three execution lanes: fast control, fast read and agent.
- Adds explicit execution and verification metadata while preserving legacy response fields.
- Adds regression coverage for route classification and verification outcomes.

## 0.10.139

### Deterministic named Rule Machine status

- Adds direct status queries for named Rule Machine rules and exact Rule IDs.
- Reports disabled, paused and active states separately.
- Supports safe shortened-name clarification without automatic writes.

## 0.10.138

### Rule write capability diagnostics

- Reports disabled, paused and active rule state separately when a requested write is unsupported.
- Provides a developer-ready MCP rule enable/disable contract without substituting pause for disable.

## 0.10.137

### Separate pause and disable semantics

- Keeps pause/resume separate from enable/disable.
- Refuses unsupported rule disable writes instead of silently pausing a rule.

## 0.10.136

### Safe shortened Rule Machine matching

- Adds ranked clarification candidates for shortened Rule Machine names.
- Preserves exact Rule ID confirmation before writes.
- Rejects unsafe broad one-word matching.

## 0.10.135

### Room climate ranking filters

- Excludes appliance, fridge and freezer sensors from room humidity and temperature rankings.
- Requires a real Hubitat room assignment before a climate reading can participate in room comparisons.
- Keeps deterministic highest and lowest climate answers grounded in verified live measurements.
- Adds regression coverage for appliance and unassigned sensor exclusions.

## 0.10.134

### Deterministic climate extrema and semantic evidence fix

- Answers highest and lowest humidity or temperature questions directly from verified live measurements.
- Prevents AI synthesis from inventing room names or unsupported sensor values.
- Ignores aggregate and invalid climate readings when selecting extrema.
- Fixes the undefined `environmental_insights` variable in semantic home evidence collection.
- Adds focused climate extrema regression coverage.

## 0.10.133

### Deterministic climate measurement routing

- Routes humidity and temperature comparison questions directly to verified live measurements.
- Prevents room inventory from being used as a substitute for sensor readings.
- Preserves AI synthesis while keeping evidence selection deterministic.
- Keeps guarded writes and the unified MCP control path unchanged.

## 0.10.132

### Unified agent reasoning helper fix

- Fixed UnifiedAdaptiveMCPAgent reasoning filter invocation
- Restored correct instance method behaviour for `_looks_like_reasoning`
- Preserved unified Ollama agent routing and deterministic MCP control
- Passed full regression release gate

## 0.10.131

### Unified HomeBrain telemetry

- Updated semantic response labels to match the unified agent architecture
- Improved Home evidence and Home attention route descriptions
- Preserved deterministic MCP control and verified state handling
- Passed complete 280-test release gate

## 0.10.130

### Unified Ollama agent authority

- Consolidated Ollama runtime decision path into UnifiedAdaptiveMCPAgent
- Removed legacy adaptive/final answer runtime duplication
- Improved cloud/local model routing consistency
- Preserved deterministic MCP control path
- Added regression coverage for unified agent behaviour

## 0.10.129

- Consolidated the maintained Ollama runtime into a substantially flatter
  inheritance chain.
- Moved adaptive cloud routing, final-answer enforcement, verified-evidence
  quality routing and the natural answer pipeline into the unified agent.
- Retained the former agent classes as compatibility implementations for
  existing imports and focused regression tests.
- Preserved local fallback, Ollama Cloud, MCP evidence recovery, final-answer
  sanitization and planner routing behaviour.
- Added architecture coverage for the reduced live runtime chain.
- Passed the complete 280-test blocking release gate.

## 0.10.128

- Split terminal entity reads into focused handlers for power accounting,
  complete device inventory, explicit device lookup and attribute reads.
- Retained one shared deterministic entity-resolution path for ambiguity,
  room matching and confidence checks.
- Preserved existing MCP calls, response dictionaries and user-visible wording.
- Added focused regression coverage for the terminal-read dispatcher order.

## 0.10.127

- Improved targeted MCP device recovery by extracting the requested device name before authoritative lookup.
- Strengthened planner guidance so discovery tools are followed by authoritative MCP reads.
- Centralized release metadata in `release_version.py`.
- Updated repository validation and release tests to use the shared version source.
- Made historical regression audits explicitly non-blocking while retaining the blocking release gate.
- Removed obsolete PWA manifest, service-worker, installation and cache-cleanup support.
- Preserved the standard Home Assistant ingress Web UI.
- Migrated FastAPI startup and shutdown handling to lifespan management.
- Preserved device-index warming, active-request cancellation and MCP/Ollama shutdown behavior.

## 0.10.86

- Deferred redundant legacy Ollama agent construction during maintained startup.
- Preserved standalone `app.py` compatibility.
- Added regression coverage proving `UnifiedAdaptiveMCPAgent` remains the final runtime agent.
- Normalized current control-routing tests to inspect `entrypoint_core.py`.
- Updated control-routing tests for current rescue, combined-level, postfix, and fallback wiring.
- Made cloud control fallback tests independent of global installer order.

# Hubitat MCP AI changelog

## 0.10.75

- Replaces the generic **Available** label in the all-device inventory with a
  deterministic primary live state such as On, Open, Active, Locked, Heating,
  temperature, humidity, power, battery or health.
- Normalizes dictionary and list-shaped Hubitat compact states without issuing
  a separate detail request for every device.
- Shows **State unavailable** when the compact inventory genuinely contains no
  recognized live state, and keeps disabled devices clearly marked.

## 0.10.74

- Routes **find/list/show all devices** to a deterministic Hubitat inventory
  response instead of treating `all devices` as a single device name.
- Returns total device, room and disabled counts plus a scrollable device list
  from one authoritative `hub_list_devices` call.
- Preserves targeted identity lookups such as **Find Freezer** and room-scoped
  inventory requests such as **Find hallway devices**.

## 0.10.73

- Resolves the main thermostat from `hub_list_devices`, then reads its complete
  live attributes through the gateway-translated `hub_get_device` operation.
- Prevents compact inventory temperature data from being mistaken for a complete
  thermostat response when the heating setpoint exists only in device detail.
- Keeps the exact **What is thermostat setpoint** request at the deterministic
  HTTP boundary and reports the separate room temperature, heating setpoint and
  cooling setpoint values without an AI clarification.

## 0.10.70

- Installs the deterministic thermostat controller inside the final runtime route bridge immediately before `/api/ask` is captured.
- Prevents exact questions such as **What is the thermostat setpoint** from falling through to generic AI device search.
- Adds regressions for the reported phrase and for final route-installation order.
- Continues to report room temperature, heating setpoint and cooling setpoint as separate live attributes.

## 0.10.69

- Reads thermostat temperature and setpoints from a fresh `hub_read_devices` call instead of inventory-only metadata.
- Adds a deterministic thermostat-status response that reports room temperature, heating setpoint and cooling setpoint separately.
- Uses the same live thermostat evidence to correct **What's happening?** summaries before they reach the Web UI.
- Falls back to the device index only when the live MCP read is unavailable.

## 0.10.68

- Prevents AI home summaries from describing measured thermostat room temperature as a setpoint.
- Treats `temperature` as the current measured value and `heatingSetpoint` or `thermostatSetpoint` as the heating target.
- Corrects the known failure mode from authoritative device-index evidence before the response reaches the Web UI.
- Records the measured temperature, actual heating setpoint and incorrect claimed value in the response diagnostics.

## 0.10.67

- Wires the enhanced Hub health tiles into the actual final `application.ask` response chain.
- Promotes database size from the old note into a dedicated tile in the live Web UI.
- Shows installed firmware and the precise software-update state, including the available version when supplied by Hubitat.
- Uses the MCP response already attached by request tracing and does not make a duplicate hub call.

## 0.10.66

- Shows the Hubitat software update state as a dedicated **Software update** tile in Hub health.
- Displays the installed firmware as **Installed firmware** and includes the available version when an update exists.
- Promotes Hubitat database size from a note into its own **Database size** tile.

## 0.10.65

- Adds an **Apps** smart shortcut beside **Rules** in the HomeBrain Web UI.
- The shortcut sends the deterministic command `List apps`.
- Injects the shortcut at the final runtime rendering layer so existing Web UI composition remains unchanged.

## 0.10.64

- Retries `hub_update_firmware` exactly once when HomeBrain has independently verified a fresh backup but the MCP firmware guard still reports `BACKUP REQUIRED`.
- Waits four seconds for the MCP backup index to settle before retrying.
- Never creates a second backup or repeats the user confirmation during the retry.
- Reports a specific backup-index-lag result when the retry is still rejected.

## 0.10.63

- Removes the `mcp_tool_catalogue.py` startup handler that reset the running application to `0.10.56`.
- Keeps the version baked into `/app/.homebrain-build-version` as the sole runtime authority.
- Adds a startup regression proving the MCP tool catalogue installer cannot mutate application or API versions.
- Keeps the authoritative rendered-version diagnostic introduced in 0.10.62.

## 0.10.62

- Rewrites the Web UI's embedded JavaScript version after every renderer and UI patch has completed.
- Adds `/api/runtime-version` with baked, application, API and rendered versions for direct diagnosis.
- Fails loudly if the generated HomeBrain page does not contain exactly one replaceable version declaration.
- Keeps the baked container version as the single authoritative release value.

## 0.10.61

- Bakes Home Assistant `BUILD_VERSION` into every add-on image so each release invalidates Docker build cache.
- Reads the running image version from `/app/.homebrain-build-version` instead of trusting repository metadata alone.
- Adds Home Assistant image labels for the build version and architecture.
- Keeps the non-PWA ingress UI and guarded deterministic app controller.

## 0.10.60

- Removes the installable PWA layer from the Home Assistant ingress page.
- Unregisters legacy HomeBrain service workers and deletes `hubitat-mcp-ai-shell-*` caches.
- Keeps a temporary cleanup worker endpoint so previously registered workers can retire themselves.
- Adds cache-clearing response headers while preserving the guarded app-controller route.

## 0.10.59

- Replaces the stale cache-first PWA service worker with network-only navigation handling.
- Deletes all historical `hubitat-mcp-ai-shell-*` caches when the new worker activates.
- Adds a one-time browser cache reset and an `X-HomeBrain-Version` response header.
- Prevents Home Assistant ingress from displaying an older HomeBrain release after the add-on has updated.

## 0.10.58

- Rebinds the final `/api/ask` endpoint after the guarded app controller is installed, so explicit app commands cannot fall through to generic AI device handling.
- Rebuilds the Web UI home route from the live runtime version instead of a release value captured during `entrypoint_core` import.
- Adds no-store headers to the rendered HomeBrain page so the displayed version cannot remain frozen after the add-on has updated.

## 0.10.57

- Adds deterministic Hubitat app inventory with enabled, disabled, and unknown counts.
- Adds guarded app enable/disable commands through `hub_set_app_disabled`.
- Requires clickable confirmation before every app write and resolves confirmed actions by exact App ID.
- Verifies changes from the write response and an independent `hub_list_apps` read-back when available.
- Keeps ordinary device enable/disable commands outside the app controller unless the request explicitly says app or application.

## 0.10.56

- Adds a live, deterministic MCP app-management capability diagnostic.
- Reports app inventory, app state read-back, and app enable/disable write support separately.
- Includes a developer-ready suggested MCP contract when support is missing.
- The diagnostic is read-only and never changes an app.

Previous release history is preserved in `CHANGELOG-history-through-0.10.55.md`.
