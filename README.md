# HomeBrain OS

AI-ready smart home operating system for Hubitat and Home Assistant.

HomeBrain OS runs as a Home Assistant add-on, connects to Hubitat via Maker API, normalises devices into a clean internal model, and exposes a mobile-friendly dashboard/API.

## Current status

`v0.7.6-alpha` assistant dashboard:

- Home Assistant OS add-on structure
- Hubitat Maker API integration
- SQLite device cache in `/data/homebrainos.sqlite3`
- Device normalisation and room inference
- Live dashboard and room APIs
- Unified text/voice command engine
- Assistant API with diagnostics and optional local Ollama answers
- Switch, sensor, and device attribute normalization
- Automatic Hubitat per-device state refresh when list data is incomplete
- Glanceable dashboard cards with noisy raw attributes hidden
- TRV thermostat setpoint controls
- Heating mode voice/text commands
- Heating commands raise TRV setpoints above measured room temperature when needed
- Mobile web UI
- CI validation
- Release packaging workflow

## Install on Home Assistant OS

Add this repository URL in the Home Assistant Add-on Store:

```text
https://github.com/ienam-smarthome/HomeBrainOS
```

For local development, copy `homebrainos` to your Home Assistant `/addons/homebrainos` folder, reload the Add-on Store, configure options, then install/start the add-on.

Required options:

```yaml
hubitat_base_url: http://192.168.1.239
maker_api_app_id: "4143"
maker_api_token: your-token-here
refresh_seconds: 30
```

## Development roadmap

- `v0.5.0-alpha` Device engine + SQLite cache
- `v0.6.0-alpha` Live dashboard + rooms
- `v0.7.1-alpha` Assistant diagnostics + richer device attributes
- `v0.7.2-alpha` Automatic device-state detail refresh
- `v0.7.3-alpha` Cleaner dashboard cards
- `v0.7.4-alpha` TRV setpoint controls
- `v0.7.5-alpha` Heating mode assistant commands
- `v0.7.6-alpha` Heating commands raise setpoints above room temperature
- `v0.8.0-alpha` Deeper Ollama AI router
- `v1.0.0-beta` Stable core

## Security

Never commit Maker API tokens, local IP credentials, `.env` files, or database/cache files containing personal home data.
