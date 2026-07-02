# Changelog

## v0.6.0-alpha

- Align add-on, API, and documentation version metadata.
- Add dashboard command support for refreshing the device cache.
- Harden Maker API URL generation for special characters in credentials.
- Improve room API efficiency by avoiding repeated cache reads.
- Improve Hubitat device state parsing for Maker API `currentStates`, dictionary attributes, and mixed-case values.

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
