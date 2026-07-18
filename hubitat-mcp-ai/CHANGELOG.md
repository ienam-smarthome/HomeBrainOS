# Hubitat MCP AI changelog

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
