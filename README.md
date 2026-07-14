# HomeBrain OS

AI-ready smart home operating system for Hubitat and Home Assistant.

HomeBrain OS runs as a Home Assistant add-on, connects to Hubitat via Maker API, normalises devices into a clean internal model, and exposes a mobile-friendly dashboard/API.

Short GitHub description: Local-first AI smart-home dashboard and assistant for Hubitat + Home Assistant, with event-driven state, room intelligence, and privacy-preserving local control.

## Current status

`v1.9.34-alpha` assistant dashboard:

- Home Assistant OS add-on structure
- Hubitat Maker API integration
- SQLite device cache in `/data/homebrainos.sqlite3`
- Device normalisation and room inference
- Live dashboard and room APIs
- Unified text/voice command engine
- Assistant API with diagnostics, live event intelligence, and optional local Ollama answers
- Smart Home Intelligence answers for natural questions such as “why are 3 lights on?”
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
- Voice station mode via `?station=1` for a monitor/tablet/browser that listens for `Hey HomeBrain`
- Singular light/switch questions such as `what light is on` are understood
- Spoken light/switch answers are direct names without reading the text heading
- Mic button cancels current speech before listening
- Heating on/off commands adjust setpoints only and do not send thermostat mode off/on commands
- Numbered device commands such as `livingroom light 1` stay targeted to that device
- Singular ambiguous commands ask for the exact device instead of guessing
- Dimmer level commands such as `set bedroom 1 light to 30 percent`
- Room brightness commands such as `increase brightness in hallway`
- Backend level API for dimmable device controls
- Weather summaries from Hubitat weather devices such as Weather Open-Meteo
- Recent Hubitat log diagnostics with token redaction and affected-device hints
- Visible selected feedback when tapping summary, room, and shortcut tiles
- Persisted mute-audio toggle for spoken assistant responses
- Simplified room detail output without raw attribute dumps
- Structured local AI context pack for Ollama with summary, weather, hub health, diagnostics, active rooms, and device facts
- Deterministic command-first routing so basic device commands still execute immediately when local AI is offline
- Dashboard header version is read from the running API, and voice commands ignore dangling filler like `to`
- Hubitat Maker API event webhook for immediate cache updates from pushed device events
- Event-driven dashboard refresh so summary pills and tiles update as pushed states arrive
- Active-room answers list only active/on device names instead of inactive/off counts
- Room-on and room-detail answers use practical active-state phrases such as on, heating, open, unlocked, present, leak detected, and using power
- Stale-device checks flag motion active too long, lights left on too long, and devices that have not reported recently
- Stale-device answers show friendly hours/minutes and speak affected device names plus durations
- Deterministic state-duration answers for questions like `how long has the TV been on`
- Exact device labels such as `TV` are preferred over broader multimedia/context matches
- Last-state session answers such as `how long was the TV last on for`
- Configurable local time zone for event/session answers, defaulting to Europe/London
- Total state-time answers such as `total time TV was on today`
- Protected AI context inspection endpoint at `/api/ai/context`
- Exact heating setpoint commands such as `set hallway heating to 21`
- Room active-state questions such as `what is on in hallway`
- Timed device-on commands such as `turn on desk fan for 10 minutes`
- Pending scheduled device timers endpoint at `/api/timers`
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

Voice station mode:

```text
http://your-homebrain-host:8787/?station=1
```

Open this on the GMKTec or a dedicated display, tap `Start voice station` once, then say commands such as `Hey HomeBrain, turn off the bedroom lights`. You can also say `Hey HomeBrain`, pause briefly, then say the command during the visible 15-second countdown.

Optional hardening:

```yaml
api_token: choose-a-local-dashboard-token
```

When `api_token` is set, device commands, setpoint changes, cache refreshes, and assistant requests require the dashboard to send the token. The browser UI prompts once and stores it in local storage.

Optional local AI:

```yaml
ollama_enabled: true
ollama_base_url: http://your-ollama-host:11434
ollama_model: qwen2.5:3b
ollama_context_device_limit: 35
ollama_include_hub_logs: false
ollama_timeout_seconds: 75
ollama_num_predict: 90
ollama_health_timeout_seconds: 2
ollama_health_cache_seconds: 60
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
- `v0.7.34-alpha` Dimmable light level commands and ambiguity prompts
- `v0.7.35-alpha` Weather summaries, hub log diagnostics, and room brightness commands
- `v0.7.36-alpha` Clear tapped/loading feedback for dashboard tiles
- `v0.7.37-alpha` Structured Ollama AI context pack and context inspection
- `v0.7.38-alpha` Exact heating setpoints, room active-state answers, and timed device-on commands
- `v0.7.39-alpha` Mute-audio toggle and quieter tile selection feedback
- `v0.7.40-alpha` Simplified room detail output
- `v0.7.41-alpha` Persistent scheduled device timers with dashboard cancel controls
- `v0.7.42-alpha` Delayed start commands such as `turn on hallway lights in 15 seconds`
- `v0.7.43-alpha` Batched stale device detail refresh for devices that do not update reliably from Maker API lists
- `v0.7.44-alpha` Longer Ollama timeout and shorter local-LLM answers for Home Assistant add-on use
- `v0.7.51-alpha` Voice station shows a command countdown and suppresses harmless mobile no-speech resets
- `v0.7.52-alpha` Voice cleanup and room-aware fuzzy device targeting before Ollama fallback
- `v0.7.53-alpha` Dynamic Web UI version label and trailing voice-filler cleanup
- `v0.7.54-alpha` Hubitat event webhook updates cached device state immediately
- `v0.7.55-alpha` Browser state-event stream refreshes summary pills and tiles immediately
- `v0.7.56-alpha` Active rooms list only active/on device names
- `v0.7.57-alpha` Room status answers reuse practical active-state phrases and avoid inactive device filler
- `v0.7.58-alpha` Stale-device checks for stuck motion, lights left on, and quiet devices
- `v0.7.59-alpha` Stale-device reports use friendly elapsed times and spoken device details
- `v0.7.60-alpha` Deterministic state-duration answers use latest HomeBrain/Hubitat state changes
- `v0.7.61-alpha` Exact device targeting for state-duration questions and last-on session answers
- `v0.7.62-alpha` State-duration/session answers display times in the configured local timezone
- `v0.7.63-alpha` Total state-time answers for questions such as `total time TV was on today`
- `v0.7.50-alpha` Voice station keeps the command window visible across mobile speech-recognition restarts
- `v0.7.49-alpha` Phone-friendly voice station wake phrase arming for separate wake and command phrases
- `v0.7.48-alpha` Browser voice station mode with `Hey HomeBrain` wake phrase filtering
- `v0.7.47-alpha` Cached Ollama health checks so local AI is skipped quickly when the PC is off
- `v0.7.46-alpha` More complete local-LLM answers with a higher default token cap and truncation marker
- `v0.7.45-alpha` Faster Ollama responses with compact AI context and shorter default answers
- `v0.8.0-alpha` Deeper Ollama AI router
- `v1.0.0-beta` Stable core

## Security

Never commit Maker API tokens, local IP credentials, `.env` files, or database/cache files containing personal home data.

### v0.9.7 Event-driven state engine

HomeBrainOS now serves dashboard and AI state answers from its SQLite/event cache by default instead of forcing Maker API refreshes on every dashboard poll. Automatic live sync is disabled by default to reduce Hubitat load; use **Refresh from Hubitat** or `/api/state-sync` for manual resynchronisation if Hubitat events are not configured.

Recommended Hubitat setup: configure Maker API event POST/callback to `http://<homebrain-host>:8787/api/hubitat/events` so HomeBrain receives device state changes and updates the dashboard via server-sent events.


### v1.0.1-alpha UI Live Push + Event Filtering

HomeBrain now uses the Hubitat event stream to update dashboard summary pills live, while filtering noisy non-dashboard attributes from UI pushes.


### Event diagnostics

Use `/api/event-diagnostics` to confirm Hubitat events, UI-relevant events, ignored noisy events, SSE clients, and recent processed events.


### 1.3.0-alpha
- HomeBrain Language Engine: duration/history queries such as “lights on time today”.


### 1.4.0-alpha

Smart Home Dashboard shortcuts: the main page now prioritises everyday questions such as what's happening, attention needed, lights, light hours, energy, heating, family, timeline, and AI insights. Developer/maintenance tools are grouped separately.
