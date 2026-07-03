# Changelog

## v0.7.20-alpha

- Read Hub Info labels such as Free Mem, CPU Load/Load%, DB Size, Last Restart, Uptime, and Temperature.
- Parse Hub Info metrics from structured attributes or the Hub Info HTML/text table.

## v0.7.19-alpha

- Prefer Hubitat room assignments over label-based room inference.
- Sort active rooms alphabetically before inactive rooms.
- Treat rooms as active only when a light is on or motion is active, not when only sockets/switches are on.

## v0.7.18-alpha

- Merge compact numbered room names such as `Bedroom1` with spaced names such as `Bedroom 1`.
- Canonicalize cached room names in the rooms API so duplicate room tiles disappear without requiring a cache clear.

## v0.7.17-alpha

- Add a Hub health assistant shortcut that reads CPU, memory, and uptime metrics from the Hub Info device.
- Rename shortcut buttons to clarify app diagnostics, Hub health, device issues, refresh from Hubitat, and cache rebuild actions.
- Sort rooms with active lights, switches, sockets, or motion before inactive rooms.

## v0.7.16-alpha

- Show room socket/switch counts instead of a misleading lights tile for socket/appliance-only rooms.
- Add room power signals when power readings are available.
- Count switched sockets/appliances in active-room assistant answers.

## v0.7.15-alpha

- Refine room tiles to focus on lights, motion, and available temperature/humidity readings.
- Replace duplicated quick-action labels with clearer assistant shortcuts for status, health, active rooms, heating, and cold rooms.
- Add assistant answers for active rooms, cold rooms, heating status, and device health shortcuts.

## v0.7.14-alpha

- Simplify room summary cards with a cleaner stat grid.
- Exclude fridge meter readings from home and room average temperature/humidity.

## v0.7.13-alpha

- Make dashboard summary tiles clickable so each tile opens its matching assistant explanation.
- Show only people currently home in the People summary tile.
- Display whole-house power in kW when the value is greater than 999W.

## v0.7.12-alpha

- Link the dashboard power summary to the Octopus whole-house meter.
- Track Enamul, Samah, Tahmid, and Muhsena in the people summary tile.
- Add assistant answers for summary tile details including low batteries, active motion sensors, people, and whole-house power.

## v0.7.10-alpha

- Highlight selected On/Off buttons in green to match active device cards.
- Highlight active thermostat setpoint controls in green and keep inactive controls dimmed.

## v0.7.9-alpha

- Route `turn on heating in hallway` and similar phrases to Hallway thermostat/TRV devices only.
- Keep heating commands ahead of generic switch parsing so lights/cameras are not matched by mistake.

## v0.7.8-alpha

- Show TRV setpoint buttons as simple `-` and `+` controls.
- Dim inactive/off device cards and highlight active/on device cards.
- Dim inactive rooms and highlight rooms with active lights, switches, or motion.
- Classify TRV battery child devices as battery sensors instead of climate controls.

## v0.7.7-alpha

- Exclude TRV battery/sensor child devices from heating commands.
- Make `turn off heating` set thermostat mode off and lower high setpoints to the configured off value.
- Add configurable `heating_on_delta` and `heating_off_setpoint` options.
- Redact Maker API tokens from command error messages.

## v0.7.6-alpha

- Make `turn on heating` raise each TRV heating setpoint above its measured room temperature when needed.
- Leave TRVs with already-higher setpoints unchanged.

## v0.7.5-alpha

- Add assistant commands for `turn on heating` and `turn off heating`.
- Support room-targeted heating mode commands such as `turn on hallway heating`.
- Send `setThermostatMode/heat` or `setThermostatMode/off` to Hubitat thermostat/TRV devices.

## v0.7.4-alpha

- Replace TRV thermostat On/Off buttons with -1/+1 heating setpoint controls.
- Add a setpoint adjustment API that sends `setHeatingSetpoint` to Hubitat Maker API.
- Keep thermostat devices out of regular switch command routing.

## v0.7.3-alpha

- Reduce dashboard card noise by showing only the most useful attributes for each device type.
- Hide verbose raw Hubitat attributes from cards while keeping them available through APIs.
- Tighten controllable-device filtering for thermostat-like devices.

## v0.7.2-alpha

- Automatically fetch Hubitat per-device detail records when the device list does not include usable attributes.
- Use detail refresh to populate switch, sensor, meter, and thermostat states without requiring an on/off command.
- Keep sensor and meter devices out of the controllable-device grid unless Hubitat explicitly reports switch support.
- Show switch state as an attribute chip instead of reporting no attributes.

## v0.7.1-alpha

- Normalize switch, sensor, thermostat, safety, and power attributes across Hubitat attribute shapes and casing.
- Keep device capabilities and commands in the device model for better switchable-device detection.
- Show richer attribute chips on dashboard switch/device cards.
- Add room-level switch, motion, low-battery, and power details.

## v0.7.0-alpha

- Add `/api/assistant` as the main smart-home assistant endpoint.
- Add assistant help, diagnostics, room device listing, safer command routing, and home-level attribute answers.
- Add optional local Ollama answer support for explanatory questions without allowing LLM-driven device control.
- Update the dashboard prompt and quick actions for assistant workflows.

## v0.6.4-alpha

- Prune cached devices that no longer exist in Hubitat Maker API.
- Add a clear-cache refresh endpoint and dashboard button for removing stale persisted devices.

## v0.6.3-alpha

- Preserve last known switch states during Hubitat refreshes when Maker API omits switch values.
- Stop classifying illuminance/light sensors as controllable lights.

## v0.6.2-alpha

- Update the SQLite cache immediately after successful switch commands so summary counts and switch cards reflect the new state.
- Show explicit on/off state badges and disable the button for the current switch state.

## v0.6.1-alpha

- Add direct switch controls and clearer command feedback for matched and non-switchable devices.
- Improve Hubitat device state parsing for Maker API `currentStates`, dictionary attributes, and mixed-case values.

## v0.6.0-alpha

- Align add-on, API, and documentation version metadata.
- Add dashboard command support for refreshing the device cache.
- Harden Maker API URL generation for special characters in credentials.
- Improve room API efficiency by avoiding repeated cache reads.

## v0.5.0-alpha

- Add SQLite-backed device cache in the Home Assistant add-on.
- Add automatic background refresh from Hubitat Maker API.
- Add room inference and richer device classification.
- Add `/api/rooms` and filtered `/api/devices` endpoints.
- Add unified command/query engine for dashboard, typed commands, and voice.
- Add room-aware light control and generic attribute queries.
- Improve mobile dashboard with live room cards.


## v0.4.0-alpha

- Add complete repository structure.
- Add Home Assistant add-on scaffold.
- Add FastAPI backend.
- Add Hubitat Maker API client.
- Add device normalisation service.
- Add dashboard summary API.
- Add mobile-friendly frontend.
- Add GitHub Actions validation and packaging workflows.
