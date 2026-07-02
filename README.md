# HomeBrain OS

AI-ready smart home operating system for Hubitat and Home Assistant.

HomeBrain OS runs as a Home Assistant add-on, connects to Hubitat via Maker API, normalises devices into a clean internal model, and exposes a mobile-friendly dashboard/API.

## Current status

`v0.6.4-alpha` smart dashboard:

- Home Assistant OS add-on structure
- Hubitat Maker API integration
- SQLite device cache in `/data/homebrainos.sqlite3`
- Device normalisation and room inference
- Live dashboard and room APIs
- Unified text/voice command engine
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
- `v0.7.0-alpha` Voice assistant
- `v0.8.0-alpha` Ollama AI router
- `v1.0.0-beta` Stable core

## Security

Never commit Maker API tokens, local IP credentials, `.env` files, or database/cache files containing personal home data.
