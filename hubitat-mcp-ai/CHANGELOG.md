# Hubitat MCP AI changelog

## 0.4.28-alpha

- Fixes the result Copy button on direct `http://` access and Home Assistant ingress by running the legacy clipboard command synchronously inside the user tap.
- Uses the secure Clipboard API only when available and falls back to a visible, preselected full-result text box instead of failing silently.
- Copies the result title, answer and Technical details together, with clear `Copied`, `Text selected` or failure feedback.
- Accepts Hubitat's authoritative recent `lastBackupEpoch` when the backup-list gateway omits or misorders a newly created local backup.
- Checks filename evidence first, then `hub_get_info`, and only then considers another confirmed backup request.

## 0.4.27-alpha

- Recognises current Hubitat whole-hub manual backup filenames such as `Hub_C8_Pro_2026-07-19~2.5.1.131~manual.lzf`.
- Requests up to 100 local backup records so a newly created backup cannot be hidden when the MCP server returns older backups first.
- Treats a local whole-hub filename carrying today's date as verified recent backup evidence without guessing an exact creation time.
- Separates older dated filenames from genuinely unparseable entries in diagnostics.
- Reuses the existing timeout-aware backup creation and strict `hub_manage_backup` verification paths.

## 0.4.26-alpha

- Fixes backup verification being falsely routed through `hub_read_apps_code` when generic gateway catalogue probing encountered the text `hub_list_backups` inside app source or documentation.
- Allows backup listing only through the direct `hub_list_backups` core tool or the authoritative `hub_manage_backup` gateway.
- Ignores stale or incorrect hidden-tool gateway mappings for backup safety checks.
- Accepts both structured backup objects and plain local `.lzf`/`.zip` filenames when verifying a recent backup.
- Adds diagnostics for the exact request tool, strict gateway mode, response shape, parsed rows and unparseable backup names.
- Keeps the timeout-aware polling and duplicate-backup prevention introduced in 0.4.25-alpha.

## 0.4.25-alpha

- Detects the blank timeout exception produced when whole-hub backup creation exceeds the normal 25-second MCP request timeout.
- Polls `hub_list_backups` after a timed-out or explicitly in-progress backup call and proceeds only when a recent backup is verified.
- Records the exception type and post-create verification checks so an empty error string can no longer hide the cause.
- Remembers that a confirmed backup may still be running and prevents repeated Create presses from launching duplicate backups for two minutes.
- Keeps every Rule Machine write blocked until backup completion is verified.

## 0.4.24-alpha

- Fixes the native Rule Machine backup preflight to call `hub_create_backup` with the MCP-required `confirm=true` after the user explicitly presses Create.
- Reads the mandatory best-practice acknowledgment key from both `best_practice_reference` and the tool-specific `backup` guide.
- Accepts current MCP guide wording such as `Acknowledgment key:` in addition to older `bestPracticeKey` fields.
- Records whether confirmation and the acknowledgment key were sent without exposing the key value in technical details.
- Keeps all rule writes blocked until the backup call succeeds or a recent local backup is verified.

## 0.4.23-alpha

- Verifies existing whole-hub local backups through `hub_list_backups(scope='hub_local')` before requiring a new backup.
- Accepts a verifiable local backup from the last 24 hours, matching the MCP server's destructive-write safety requirement.
- Corrects the backup-tool model: `hub_create_backup` is a separate flat core tool, while `hub_manage_backup` only lists, restores and deletes backups.
- When no recent backup exists and the core create tool is absent, points directly to MCP Rule Server > Settings > Advanced: Per-tool Overrides and `Reset all overrides`.
- Keeps all native Rule Machine writes blocked until backup preflight succeeds.

## 0.4.22-alpha

- Recovers `hub_create_backup` when the MCP server hides it inside a generic management gateway whose compact description does not enumerate every child tool.
- Falls back from direct-tool and cached gateway-map lookup to live catalogue probing across safe MCP management gateways.
- Invokes the discovered backup tool through its owning gateway with the best-practice key intact.
- Keeps the washing-machine Rule Machine creation blocked until a recent backup is verified or successfully created.
- Improves the blocked message so it distinguishes a genuine disabled backup/admin tool from a HomeBrain discovery miss.

## 0.4.21-alpha

- Compiles the grounded `washing-complete` recommendation into a native Hubitat Rule Machine rule.
- Uses a two-stage power guard: power above 10 W arms the cycle, then power below 5 W continuously for three minutes marks completion.
- Creates a numeric Rule Machine local variable, `cycleArmed`, so ordinary standby power cannot send false finished notifications.
- Creates the shell paused, adds and verifies the local variable, reasserts pause, then adds the two triggers and guarded actions while the rule remains paused.
- Stops safely before adding triggers/actions when the local-variable write is rejected or partial.
- Keeps the Notification recipient exact and requires review plus a separate Enable action.

## 0.4.20-alpha

- Makes duplicate exact-device matches actionable by showing each Hubitat device ID and room instead of repeating the same label.
- Adds a direct `capabilityFilter=Notification` lookup for fridge-door rule drafts when the general detailed-device catalogue omits a mobile device's capabilities or commands.
- Intersects notification results with the current selected-device membership list so an unselected or stale metadata record cannot become a recipient.
- Reports multiple selected Notification devices with IDs and refuses to guess which phone should receive alerts.
- Keeps native Rule Machine creation paused and guarded exactly as in 0.4.19-alpha.

## 0.4.19-alpha

- Adds native Hubitat Rule Machine creation for MCP Rule Server 3.4.x through `hub_set_rule` and `hub_set_rule_paused`.
- Builds the fridge-door rule using the current native trigger/action schema rather than the legacy MCP child-rule engine.
- Creates an empty Rule Machine shell, pauses it before adding triggers/actions, populates it while paused, and leaves Enable as a separate explicit action.
- Reads the MCP best-practice acknowledgment key, verifies or creates the required recent hub backup, and uses stable operation tokens for retry-safe creation.
- Uses Contact open-for-two-minutes and Contact closed triggers, Notification actions, a cancelable five-minute delay, and close-trigger cancellation.
- Does not expose a misleading dry-run button because the current native Rule Machine API can execute actions but does not provide a genuine action-free simulation.

## 0.4.18-alpha

- Recovers automatically when the MCP server changes between consolidated category gateways and the flat tool catalogue.
- Detects the server's explicit `useGateways is OFF` response, refreshes `tools/list`, clears the stale gateway map, and retries the originally requested tool directly.
- Prevents a gateway-mode change from breaking live device reads until the HomeBrain add-on is restarted.

## 0.4.17-alpha

- Adds `ollama_prefer_cloud_response`, enabled by default, so upgraded installations use `gemma4:31b-cloud` even when Home Assistant preserves an older saved `ollama_model: qwen3.5:4b` value.
- Keeps `qwen3.5:4b` as the local MCP planner and automatic Cloud fallback.
- Replaces the local-only diagnostics card with hybrid diagnostics showing Cloud registration, effective response model, planner, fallback and last-agent state separately.
- Clearly reports when an older saved response model is being overridden by the explicit Cloud preference.
- Allows deliberate local-only synthesis by turning off Prefer Cloud response.

## 0.4.16-alpha

- Adds a guarded automation rule workflow: recommendation → reviewable draft → explicit create confirmation → dry-run test → enable/disable.
- Learns rule tool names and input schemas from the connected MCP server at runtime, supporting current `create_rule`/`update_rule`/`test_rule` tools and older gateway-prefixed variants.
- Creates rules with `enabled=false` or an equivalent paused/draft flag and refuses writes when the server schema cannot guarantee a disabled initial state.
- Compiles the fridge-door recommendation into documented MCP rule JSON with open-duration and close triggers, notification actions, a delayed repeat, and cancellation when the contact closes.
- Requires exactly one selected Notification-capable device before compiling a phone-notification rule; HomeBrain never guesses the recipient.
- Blocks duplicate rule names and keeps dry-run, enable, and disable as separate explicit operations.
- Adds mobile action buttons for Build rule, Create disabled rule, Dry-run test, Enable rule, Disable rule, and Cancel.

## 0.4.15-alpha

- Makes the compact live MCP device summary the authoritative selected-device membership list.
- Prevents metadata-only devices removed from the MCP allowlist from reappearing until the 120-second metadata cache expires.
- Keeps detailed capabilities and attributes only for devices still present in the live selected list.
- Makes dashboard light/switch classification capability-aware, so dimmers and custom lights are not counted as generic switches solely because their labels omit the word `light`.
- Adds diagnostics for dropped metadata orphans and focused regression coverage for removed active sensors.

## 0.4.14-alpha

- Adds a verified automation-recommendation route for questions such as `Suggest one useful automation for the devices I have`.
- Reads the selected Hubitat device inventory directly instead of relying on the general Ollama planner to discover evidence.
- Prioritises grounded washing-machine completion, fridge/freezer door, same-room motion-lighting and humidity-ventilation candidates.
- Returns a complete deterministic trigger, action and safeguard when AI synthesis is unavailable.
- Never creates or changes a rule automatically.

## 0.4.13-alpha

- Adds `gemma4:31b-cloud` for AI response synthesis through a signed-in Windows Ollama service.
- Keeps `qwen3.5:4b` as the local MCP planner and automatic Cloud retry model.
- Keeps exact device reads, lists and controls deterministic and local to conserve Free cloud usage.
- Adds explicit Ollama Cloud/local provider badges.
- Adds a verified active-motion/nearby-off-light route using same-room Hubitat assignments.
- Adds a Windows setup script that registers and tests Cloud without storing an API key in Home Assistant.

## 0.4.12-alpha

- Recovers missing live states from the detailed device catalogue.
- Prevents missing state coverage from appearing as zero motion, zero lights or an AI-written all-clear.

## 0.4.11-alpha

- Corrects bedroom temperature grouping and preserves alternate same-room sensor readings.

## 0.1.11-alpha

- Routes offline/stale device questions directly through the MCP fast path.
- Adds a dedicated Device health result showing offline and stale counts.
- Excludes intentionally disabled devices from stale-device results.
- Avoids the 40-second Ollama wait for the Device health shortcut.

## 0.1.10-alpha

- Automatically rechecks Ollama inference after a stale timeout.
- Keeps the last question visible and restores it after refresh.
