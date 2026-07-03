# HomeBrain OS

AI-ready smart home operating system for Hubitat and Home Assistant.

HomeBrain OS runs as a Home Assistant add-on, connects to Hubitat via Maker API, normalises devices into a clean internal model, and exposes a mobile-friendly dashboard/API.

## Current status

`v0.7.33-alpha` assistant dashboard:

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
- Heating-off commands lower TRV setpoints to a configurable off value
- Dim inactive/off devices and highlight active/on rooms and devices
- Room-targeted heating commands in both `hallway heating` and `heating in hallway` forms
- Green selected-state buttons for active On/Off and heating controls
- Whole-house power summary linked to the Octopus meter
- Named people summary for Enamul, Samah, Tahmid, and Muhsena
- Assistant explanations for summary tiles, low batteries, active motion, people, and Octopus power
- Clickable summary tiles for dashboard drill-downs
- People summary lists only people currently home
- Power summary displays kW when over 999W
- Cleaner, less crowded room summary cards
- Fridge meter readings excluded from temperature and humidity averages
- Room cards focus on lights, motion, and available temperature/humidity readings
- Room cards show sockets/switches and power for appliances where available
- View options can show/hide summary, shortcuts, rooms, inactive rooms, no-signal rooms, devices, and output
- No-signal rooms such as Life360 are hidden by default
- Mobile layout is tightened for Samsung S25 Ultra-sized screens
- Spoken assistant responses use natural units such as degrees, watts, percent, and kilowatt hours
- Sticky floating microphone button for mobile voice input
- Voice shortcut mode via `?voice=1` for home-screen shortcuts and Samsung routines
- Singular light/switch questions such as `what light is on` are understood
- Spoken light/switch answers are direct names without reading the text heading
- Mic button cancels current speech before listening
- Heating on/off commands adjust setpoints only and do not send thermostat mode off/on commands
- Numbered device commands such as `livingroom light 1` stay targeted to that device
- Assistant shortcuts for status, health, active rooms, heating, and cold rooms
- Hub health shortcut reads CPU load, free memory, and uptime from the Hub Info device
- Hub health also reads DB size, last restart, and temperature from Hub Info HTML/table output
- Clearer refresh/cache shortcut labels
- Active rooms are sorted before inactive rooms
- Active room sorting uses lights-on or active motion only, then alphabetical order
- Hubitat room assignments are preferred before label-based room inference
- Numbered room names are merged, so `Bedroom1` and `Bedroom 1` show as one room
- Rooms appear before Controllable Devices, which is now collapsible
- Motion is hidden for rooms without motion sensors; app/appliance sockets show as Sockets with power where available
- Online status includes compact Hub CPU/free-memory health with color severity
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
hubitat_base_url: http://your-hubitat-ip
maker_api_app_id: "your-maker-api-app-id"
maker_api_token: your-token-here
refresh_seconds: 30
```

Mobile voice shortcut:

```text
http://your-homebrain-host:8787/?voice=1
```

Android browsers require one tap before microphone access, so voice mode opens a large tap-to-speak panel.

Optional hardening:

```yaml
api_token: choose-a-local-dashboard-token
```

When `api_token` is set, device commands, setpoint changes, cache refreshes, and assistant requests require the dashboard to send the token. The browser UI prompts once and stores it in local storage.

## Development roadmap

- `v0.5.0-alpha` Device engine + SQLite cache
- `v0.6.0-alpha` Live dashboard + rooms
- `v0.7.1-alpha` Assistant diagnostics + richer device attributes
- `v0.7.2-alpha` Automatic device-state detail refresh
- `v0.7.3-alpha` Cleaner dashboard cards
- `v0.7.4-alpha` TRV setpoint controls
- `v0.7.5-alpha` Heating mode assistant commands
- `v0.7.6-alpha` Heating commands raise setpoints above room temperature
- `v0.7.7-alpha` Safer heating off and climate device filtering
- `v0.7.8-alpha` Cleaner active/inactive dashboard states
- `v0.7.9-alpha` Room-targeted heating intent parsing
- `v0.7.10-alpha` Green selected-state controls
- `v0.7.12-alpha` Summary tile explanations and Octopus/named people tiles
- `v0.7.13-alpha` Clickable summary tiles and kW power display
- `v0.7.14-alpha` Cleaner room cards and fridge meter average exclusion
- `v0.7.15-alpha` Focused room tiles and smarter assistant shortcuts
- `v0.7.16-alpha` Socket/appliance room signals with power
- `v0.7.17-alpha` Hub health and clearer refresh/cache actions
- `v0.7.18-alpha` Numbered room name canonicalization
- `v0.7.19-alpha` Hubitat room assignment and active-room sorting
- `v0.7.20-alpha` Hub Info HTML/table metric parsing
- `v0.7.21-alpha` Room card cleanup and collapsible controllable devices
- `v0.7.22-alpha` Inline Hub health status severity
- `v0.7.23-alpha` Hub free-memory MB/GB status formatting
- `v0.7.24-alpha` Active-first alphabetical controllable device ordering
- `v0.7.25-alpha` Hub health value formatting and controllable-device availability fix
- `v0.7.26-alpha` Room tiles show motion-capable and presence-only rooms
- `v0.7.27-alpha` Clickable room details and room tile explanations
- `v0.7.28-alpha` Remove unreliable room-level presence chips
- `v0.7.29-alpha` Mobile view options and no-signal room filtering
- `v0.7.30-alpha` Natural spoken assistant units
- `v0.7.31-alpha` Floating mic button and mobile voice shortcut mode
- `v0.7.32-alpha` Direct spoken answers for singular light/switch questions
- `v0.7.33-alpha` Safer voice commands and setpoint-only heating control
- `v0.8.0-alpha` Deeper Ollama AI router
- `v1.0.0-beta` Stable core

## Security

Never commit Maker API tokens, local IP credentials, `.env` files, or database/cache files containing personal home data.
