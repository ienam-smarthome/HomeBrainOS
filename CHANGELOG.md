# Changelog

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
