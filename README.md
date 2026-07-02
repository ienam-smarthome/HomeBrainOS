# HomeBrain OS

AI-ready smart home operating system for Home Assistant OS and Hubitat.

## Current release

`v0.3.0-alpha`

This repository currently contains a Home Assistant OS add-on that connects to Hubitat Maker API, normalises device attributes, caches devices, and provides a mobile dashboard/chat interface.

## Install on Home Assistant OS

1. Copy `addon/homebrainos` into your Home Assistant `addons` share, or add this repository as a custom add-on repository when the add-on repository metadata is finalised.
2. In Home Assistant, go to **Settings → Add-ons → Add-on Store → ⋮ → Reload**.
3. Install **HomeBrain OS** from Local add-ons.
4. Configure:
   - `hubitat_base_url`
   - `maker_api_app_id`
   - `maker_api_token`
5. Start the add-on and open the Web UI.

## Security

Do not commit your Maker API token, Hubitat token, or any private home configuration to this repository.

## Roadmap

- v0.4-alpha: persistent SQLite cache
- v0.5-alpha: room pages and device cards
- v0.6-alpha: WebSocket live updates
- v0.7-alpha: Ollama / GMKtec AI router
- v1.0-beta: stable Home Assistant add-on release
