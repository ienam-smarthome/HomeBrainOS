# Hubitat MCP AI changelog

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
