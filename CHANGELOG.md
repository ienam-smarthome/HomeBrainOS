# Changelog

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
