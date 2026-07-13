## v1.9.21-alpha - JSON + Event Backlog Hotfix

- Sanitizes dashboard/status/assistant responses so stale cached NaN values return as null instead of causing 500 errors.
- Filters dashboard and room averages with finite-number checks for existing cached values.
- Drops noisy Hubitat callback attributes such as reportHtml/reportText/lastUpdated from SQLite writes and cache updates.
- Further reduces Maker API pressure with slower pacing and smaller live/detail refresh caps.

## v1.9.20-alpha - Dashboard Hotfix

- Fixes the Summary / What's Happening shortcut crash caused by non-text briefing items.
- Excludes Hub Info, weather, bridge, meter, and other system/helper devices from indoor temperature and humidity averages.
- Ignores non-finite numeric readings so invalid device values cannot break dashboard JSON responses.

## v1.9.19-alpha - Hubitat Request Stability

- Adds a global Maker API request governor so detail refreshes are serialized and paced before they reach Hubitat.
- Lowers default live/detail refresh batch sizes to avoid Hubitat pending asynchronous HTTP request buildup.
- Keeps the UI online when only dashboard data fails, and stops read-only shortcuts from triggering full dashboard/device reloads.
- Aligns active-room filtering with the backend rule: active means a light is on or motion is active.

## v1.9.8-alpha - Targeted Live Detail Polling

- Polls the live Hubitat detail endpoint for weather and TRV status when cached attributes are incomplete.
- Routes `AI status` and `Ollama status` to the settings check before room/status matching.
- Formats recent Device Events as readable lines instead of raw event dictionaries.

## v1.9.7-alpha - Clearer Device Diagnostics

- Makes the Device Events shortcut show event-stream diagnostics instead of generic device inventory.
- Makes the Device Health button open the actual health monitor summary.
- Prefers populated Open-Meteo weather records when duplicate weather devices exist in cache.
- Uses TRV `controlMode` as a heating-status fallback when `thermostatMode` is absent.

## v1.9.6-alpha - Rain-Aware Weather + Settings Check

- Routes rain and precipitation questions to the deterministic Open-Meteo weather answer.
- Extracts rain amount and precipitation chance from Open-Meteo summary text when separate attributes are missing.
- Adds a HomeBrain settings check answer for Ollama/local AI and auto live sync options.

## v1.9.5-alpha - Shortcut Routing + AI Config Clarity

- Fixed `heating status` being intercepted as a daily briefing by the local-first assistant wrapper.
- Made `which batteries are low` use the dashboard low-battery summary instead of stale replacement-report rows.
- Clarified the local AI disabled message so it points to `ollama_enabled` and `ollama_base_url` add-on options.

## v1.9.4-alpha - AI Fallback for Unknown Questions

- Sends non-control questions that HomeBrain cannot answer deterministically to local AI/Ollama when enabled.
- Keeps failed device-control requests deterministic so AI cannot imply it operated a device.
- Improves the disabled-AI message for open-ended questions.

## v1.9.3-alpha - Faster Shortcuts + Weather Detail

- Made read-only smart shortcut answers feel faster by avoiding unnecessary dashboard/device reloads after each answer.
- Expanded Open-Meteo weather answers with current conditions, rain, wind, pressure, and next forecast from the cached weather tile.
- Added natural offline aliases such as `anything offline?`.

## v1.9.2-alpha - Room Status + Encoding Fix

- Bumped the Home Assistant add-on version so HA can detect the update.
- Fixed mojibake around GBP and temperature symbols in dashboard/assistant answers.
- Routed room status prompts such as `bathroom status` to deterministic room facts before daily briefing fallback.

## 1.4.2-alpha - Performance + Intelligence Polish

- Added UI/event filtering thresholds for tiny power, demand, temperature, and humidity changes.
- Debounced non-critical summary rebuilds while keeping switch/motion/contact changes immediate.
- Added CPU Advisor shortcut to the main dashboard.
- Fixed duplicate `/api/switches` frontend call in the device loader.
- Extended event diagnostics with filter thresholds and counters.


## v1.4.1-alpha - Energy Advisor Totals

- Energy Advisor now reports energy and cost used today so far from the Octopus/whole-house meter.
- Energy Advisor now reports yesterday's energy and cost where available.
- Falls back to parsing Octopus display summary attributes when direct yesterday attributes are not exposed.

## v1.1.0-alpha - Smart Home Intelligence

- Added deterministic intelligence for questions like `why are 3 lights on?` so HomeBrain explains the active lights instead of falling back to generic diagnostics.
- Adds on-duration, room activity context, and suggestions for lights left on without recent activity.
- Treats power-only child devices such as socket power meters as sensors, reducing false unknown switch states.

## v1.2.0-alpha - Intent + Entity Parser

- Added natural room/entity resolution for questions like "how long has Bedroom two light been on today".
- Resolves spoken/typed variants such as "bedroom two", "bedroom to", "second bedroom", "BR2" style room intent before device matching.
- Duration queries now filter by room first, then device type, reducing false multi-device disambiguation.

## v1.0.1-alpha - Event Diagnostics

- Added `/api/event-diagnostics` with event stream health, last 20 events, UI relevance counts, SSE payload counts, and stale-event warning.
- Added compact event diagnostics to `/api/status`.
- Tracks ignored noisy events separately from UI-relevant events.


## v1.0.0-alpha - UI Live Push + Event Filtering

- Applied event-stream dashboard updates immediately in the browser.
- Added summary-cache-driven SSE updates so noisy events do not flood the UI.
- Filtered noisy Maker API event attributes such as RSSI, voltage, dataAgeSeconds, lastSeen, display text, and lux from UI pushes.
- Kept important live dashboard updates for switch, motion, presence, power, demand, energy, temperature, humidity, battery, and heating state.


## v0.9.7-alpha - Event-driven state engine

- Disabled automatic dashboard-triggered live Maker API detail sync by default.
- Dashboard and AI questions now read from the shared SQLite/event cache.
- `/api/switches` no longer forces a full state refresh.
- `which lights are on` and `which switches are on` no longer fetch per-device details unless manual sync is used.
- Added lower default refresh frequency and explicit live sync controls to reduce Hubitat busy time.
- Manual resync remains available through the Refresh button and `/api/state-sync`.

## v0.9.6-alpha - Reliable Live State Sync

- Added targeted live switch/light state refresh using Maker API device detail endpoints.
- Dashboard tiles now sync current light/switch states without waiting for full cache refresh.
- "Which lights are on" and "which switches are on" force a current-state sync before answering.
- Added GET support for `/api/state-sync` for quick browser testing.
- Added performance counters for live switch sync so Hubitat load can be reviewed.


## v0.9.5-alpha - Live State Sync Fix

### Fixed
- Added throttled live-state synchronisation for dashboard tiles and state-sensitive questions.
- `which lights are on`, `which switches are on`, `/api/dashboard`, and `/api/switches` now refresh Maker API state before answering when the cache is older than `STATE_SYNC_SECONDS`.
- Added `/api/state-sync` for manual state verification.
- Added performance counters for state sync attempts and skips.

### Why
- Without a Hubitat event callback, light/switch states could remain stale in the SQLite cache until the next full refresh.
- This release keeps the CPU optimisations but avoids misleading live-state answers.

## v0.9.4-alpha - Version Sync & Frontend Cache Fix

### Fixed
- Synchronised the backend APP_VERSION with the Home Assistant add-on version.
- Added `/api/version` as a lightweight single source for version checks.
- Updated the Web UI to display the exact backend version including `-alpha`.
- Added no-cache headers for `/` so the HomeBrain UI is less likely to show an old release after add-on updates.

### Why
- Home Assistant showed `0.9.3-alpha` while the Web UI still showed `v0.9.2` because the backend APP_VERSION was stale and the UI only read that backend value.

## v0.9.3-alpha - AI Device Intelligence & False Positive Reduction

### Added
- AI Device Intelligence profiles for thermostats/TRVs, energy meters, lights, smart plugs, contact sensors, motion sensors, presence sensors, climate sensors, and battery sensors.
- `/api/device-intelligence` for classification output, confidence scores, dashboard groups, suggested rooms, and ignored checks.
- Auto-exclusion list showing devices deliberately ignored for invalid switch-state checks.

### Improved
- TRVs are no longer treated as broken switches when they expose on/off commands without a switch state.
- Octopus/energy meter style devices are classified as read-only energy meters instead of controllable switches.
- Device Inspector now separates genuine switch issues from expected non-switch devices.
- Unknown room items now include intelligence metadata and stronger suggested-room confidence.

### Practical impact
- Reduces false positives in housekeeping and AI answers.
- Leaves real issues such as smart sockets with missing switch state visible for investigation.
- Provides a stronger foundation for learning mode and one-click device mapping later.

## v0.9.2-alpha - Device Inspector & Actionable Housekeeping

Added Device Inspector to make housekeeping counts actionable. HomeBrain can now list unknown switch-state devices, unassigned room devices, duplicate names, generic devices, and devices with weak capability data. Added `/api/device-inspector` and natural-language support for questions like “what are the unknowns?”.

## v0.9.1-alpha - Performance Baseline & Tomorrow Review Pack

- Added persistent performance snapshots so HomeBrain can compare load over time.
- Added actual Maker API GET counters, error counters and last-call timing.
- Added `/api/performance-baseline`, `/api/performance-compare`, and `/api/performance-snapshots`.
- Added assistant prompts for "save performance baseline" and "compare performance".
- Saved startup and scheduled performance snapshots for next-day CPU review.

## v0.9.0-alpha

Performance engineering release for high Hubitat CPU / Maker API load.

### Added
- Performance Advisor endpoint: `/api/performance-advisor`.
- Natural language support for CPU / hub load / Maker API load questions.
- Runtime counters for full refreshes, skipped refreshes, detail fetches, event updates, and estimated Maker API request rate.

### Improved
- Full refreshes are now throttled with a minimum refresh gap.
- Default background refresh reduced from 30s to 120s.
- Device detail refreshes reduced from large batches to small batches.
- Manual refresh and cache clear still force a full refresh.
- Command context refreshes now reuse cache where safe instead of repeatedly hammering Maker API.

### Goal
Reduce Hubitat busy time and excessive Maker API method calls while keeping HomeBrain responsive through cached and event-driven updates.

## v0.8.3-alpha

- Added Automation Health / Self-Check outcome verification.
- Added deterministic checks for bathroom fan/humidity behaviour, device reporting monitor, and energy waste monitor.
- Added `/api/automation-health` and `/api/automation-explain/{name}`.
- Assistant now answers: “did the fan work today?”, “which automations failed?”, and “automation health”.

## v0.8.2-alpha

- Added deterministic AI Explain answers for humidity/fan, energy, heating/cold rooms, and stale/offline device questions.
- Added room intelligence summaries for real-life room checks: occupancy, temperature, humidity, lights, power, and low batteries.
- Added "what changed" 24-hour timeline summary with most active devices.
- Added recommendations endpoint that turns Home Health insights into practical actions.
- Added APIs: `/api/what-changed`, `/api/recommendations`, and `/api/room-intelligence/{room}`.


## v0.8.1-alpha

- Added Home Health score with attention-first practical insights.
- Added AI Energy Advisor for forgotten/always-on device checks and rough monthly cost estimates.
- Added Home Timeline from Hubitat callbacks/history.
- Added Daily Home Briefing combining health, environment, occupancy, power and priority actions.
- Added API endpoints: `/api/home-health`, `/api/energy-advisor`, `/api/timeline`, `/api/daily-briefing`.

## v0.8.0-alpha - AI Device Health Monitor

- Reworked stale device checks into a more practical device health monitor.
- Fixed false stale alerts for Aqara FP1/FP2/FP300 and other mmWave/presence sensors that can legitimately stay active while a room is occupied.
- Added a separate `occupied_long` section so long presence is shown as normal occupancy, not a stale fault.
- Kept true PIR-style motion sensors under `Motion active too long`.
- Preserved real not-reporting checks based on Hubitat activity/event timestamps.
- Added configurable thresholds: `PRESENCE_OCCUPIED_INTERESTING_HOURS` and `CONTACT_OPEN_INTERESTING_HOURS`.
- Updated device health answer into sections: healthy, needs attention, offline/not reporting, battery, actionable checks, and normal occupancy.

# Changelog

## 1.4.0-alpha - Smart Home Dashboard Shortcuts

- Replaced developer-first shortcut buttons with daily-use smart-home shortcuts.
- Added one-tap access for What's happening, Attention, Lights, Light hours, Energy, Heating, Family, Timeline, AI insights, Active rooms, Cold rooms, and Weather.
- Moved maintenance actions such as Refresh from Hubitat, Clear cache, Hub logs, Event diagnostics, and AI context into a Developer tools section.

## 1.3.0-alpha - HomeBrain Language Engine
- Added deterministic natural language intent classification for duration/history queries.
- Fixed “lights on time today” so it reports light-on hours instead of control help.
- Added all-lights and room-specific lighting usage summaries for today, yesterday, and last 24 hours.


## v0.7.64-alpha

- Fix stale-device detection so the app no longer treats HomeBrain cache refreshes as proof that a Hubitat device actually reported.
- Track `last_activity_at` from Hubitat attribute timestamps, pushed Maker API events, and real value changes.
- Make `not reporting` results show confidence/source and fall back to cache-age only when HomeBrain itself has not refreshed.

## v0.7.63-alpha

- Add deterministic total state-time answers for questions such as `total time TV was on today`.
- Clip totals to the configured local day, including sessions that started before midnight.
- Keep total-time questions out of Ollama fallback so exact labels such as `TV` are not confused with related multimedia devices.

## v0.7.62-alpha

- Add a `time_zone` add-on option, defaulting to `Europe/London`.
- Format state-duration and session timestamps in the configured local timezone so HomeBrain matches Hubitat/browser time.
- Use the same local timezone helper for Hub Info restart timestamps.

## v0.7.61-alpha

- Prefer exact device labels for state-duration questions so `TV` does not match broader multimedia devices.
- Add deterministic last-state session answers for questions such as `how long was the TV last on for`.
- Keep these answers out of local AI fallback so HomeBrain does not guess the wrong device.

## v0.7.60-alpha

- Add deterministic answers for questions such as `how long has the TV been on` and `when did the TV turn on`.
- Use the latest HomeBrain history or Hubitat event row for the current state instead of letting local AI guess.
- Report the current state clearly when the requested state does not match, for example `TV is currently off, not on`.

## v0.7.59-alpha

- Format stale-device durations as friendly hours/minutes instead of raw seconds.
- Include affected device names and durations in spoken stale-device responses.

## v0.7.58-alpha

- Add stale-device checks for motion sensors active too long, lights left on too long, and devices that have not reported recently.
- Expose stale checks through assistant phrases such as `stale devices`, `lights left on`, and `not reporting`.
- Add `/api/stale-devices` plus configurable stale thresholds in the add-on options.

## v0.7.57-alpha

- Reuse one practical active-state formatter across active rooms, room status, and room detail answers.
- Show useful active details such as light level, live power, heating, open contacts, unlocked locks, presence, and leak alerts.
- Remove inactive device-name filler from room detail explanations.

## v0.7.56-alpha

- Make active-room assistant answers practical by listing only active/on devices in each room.
- Remove inactive/off counts from active-room output so rooms do not report noisy zero-state details.
- Keep no-signal rooms such as Life360 out of active-room answers.

## v0.7.55-alpha

- Add `/api/events` server-sent events for browser-side state change notifications.
- Refresh summary pills, rooms, devices, and timers immediately when Hubitat pushed events update cached state.
- Include a state event version in `/api/status` for event-driven refresh diagnostics.

## v0.7.54-alpha

- Add a Hubitat Maker API event webhook at `/api/hubitat/events`.
- Update the SQLite device cache immediately when pushed Hubitat events arrive.
- Expose last received Hubitat event status through `/api/status` for refresh diagnostics.

## v0.7.53-alpha

- Show the dashboard version from the running API so the Web UI header cannot get stuck on an old hardcoded version.
- Ignore dangling voice-recognition filler words such as `to` at the end of device commands.
- Add coverage for `turn off dehumidifier to` so noisy mobile transcripts still control the intended device.

## v0.7.52-alpha

- Run deterministic HomeBrain commands before local AI fallback, even when Ollama is enabled but offline.
- Improve voice command cleanup for punctuation, articles, and common recognition mistakes like `dehumidifer`.
- Add room-aware fuzzy device targeting so commands such as `turn on dehumidifier in bathroom` can resolve the intended device.

## v0.7.51-alpha

- Add a visible 15-second command countdown after the voice station hears the wake phrase.
- Keep station status refreshed from the armed countdown instead of transient browser speech-recognition events.
- Suppress harmless `no-speech` and `aborted` events so mobile browser restarts do not look like failures.

## v0.7.50-alpha

- Keep voice station visibly armed after the wake phrase when mobile browsers restart speech recognition between phrases.
- Extend the wake phrase command window from 10 seconds to 15 seconds for phone testing.
- Avoid reverting the station status back to `Listening for Hey HomeBrain` while waiting for the follow-up command.

## v0.7.49-alpha

- Improve voice station wake handling for phones where `Hey HomeBrain` and the command arrive as separate speech results.
- Add a 10-second armed window after the wake phrase so the next spoken phrase is treated as the command.
- Add more wake phrase variants such as `Hello HomeBrain`.

## v0.7.48-alpha

- Add `?station=1` browser voice station mode for a dedicated HomeBrain display or GMKTec browser session.
- Add a continuous speech-recognition loop that waits for `Hey HomeBrain` before sending a command.
- Add voice station start/stop controls and status feedback in the voice overlay.

## v0.7.47-alpha

- Add cached Ollama health checks using `/api/tags` so HomeBrain skips local AI quickly when the PC is asleep or offline.
- Expose local AI online/offline state in `/api/status`.
- Add separate Ollama health timeout and cache options so offline checks stay fast without reducing answer generation time.

## v0.7.46-alpha

- Raise the default Ollama response cap from 60 to 90 tokens so short AI summaries are less likely to stop mid-sentence.
- Update the Ollama prompt to prefer complete 1-2 sentence answers.
- Add a truncation marker for length-limited Ollama responses so incomplete answers are visibly marked with an ellipsis.

## v0.7.45-alpha

- Speed up local Ollama responses by sending compact JSON context instead of pretty-printed context.
- Reduce default AI context device limit to 35 and disable hub logs by default.
- Reduce default Ollama response cap to 60 tokens and instruct the model to answer in at most two short sentences.

## v0.7.44-alpha

- Add configurable Ollama timeout and response length options for local LLMs that need longer than 20 seconds.
- Default local AI model to `qwen2.5:3b`, matching the recommended GMKTec M6 Ultra setup.
- Send low-temperature, capped-length Ollama generation options to keep spoken answers concise.

## v0.7.43-alpha

- Add batched stale-device detail refreshes so important devices can update even when the Maker API device list returns stale or partial state.
- Track per-device detail refresh timestamps in SQLite.
- Add `device_detail_refresh_seconds` and `device_detail_refresh_batch` add-on options to balance freshness and Hubitat load.

## v0.7.42-alpha

- Add delayed start commands such as `turn on hallway lights in 15 seconds`.
- Treat plural room-light phrases as explicit group commands when scheduling delayed actions.
- Keep `turn on X for 10 minutes` as immediate-on plus scheduled-off behavior.

## v0.7.41-alpha

- Persist timed device commands in SQLite so scheduled actions survive browser reloads and add-on restarts.
- Add a Scheduled dashboard panel with remaining time and cancel controls.
- Restore pending timers on startup and expose timer list/cancel API endpoints.
- Keep HomeBrain voice prompts silent while the audio mute toggle is enabled.

## v0.7.40-alpha

- Simplify room tile output into short room summaries with key counts and readings.
- Replace raw per-device attribute dumps with compact active/device name lists.
- Stop showing `Loading room details...` in the output panel when a room tile is tapped.

## v0.7.39-alpha

- Add a persisted dashboard `Mute audio` toggle that cancels current speech and suppresses future spoken responses.
- Keep microphone voice input available while audio output is muted.
- Remove the visible `Loading` badge from clicked summary, room, and shortcut tiles while keeping selected-state feedback.

## v0.7.38-alpha

- Add deterministic exact heating setpoint commands such as `set hallway heating to 21`.
- Add room active-state answers such as `what is on in hallway`.
- Add timed switch commands such as `turn on desk fan for 10 minutes`, with server-side scheduled off timers.
- Expose pending scheduled device timers through `/api/timers`.

## v0.7.37-alpha

- Replace the loose Ollama prompt with a structured AI context pack.
- Include home summary, weather, hub health, diagnostics, active rooms, selected device facts, and optional hub log diagnostics in local AI context.
- Keep deterministic device control ahead of AI and instruct Ollama not to claim it has sent commands.
- Add protected `/api/ai/context` endpoint and dashboard shortcut for inspecting the local AI context.

## v0.7.36-alpha

- Add visible selected/loading states for summary tiles, room tiles, and shortcut buttons.
- Highlight the output panel while a tile response is active.
- Show immediate `Running...` or room-loading text so taps feel responsive on mobile.

## v0.7.35-alpha

- Add weather answers from Hubitat weather devices, preferring `weatherSummary`/`weatherSummaryLine`.
- Add hub log diagnostics through a configurable Hubitat logs endpoint.
- Redact Maker API tokens from fetched log diagnostics.
- Add room brightness commands such as `increase brightness in hallway` and `decrease bedroom 2 brightness`.
- Add Weather and Hub logs dashboard shortcuts.

## v0.7.34-alpha

- Add voice/text dimmer level commands such as `set bedroom 1 light to 30 percent`.
- Ask for a more exact device name when a singular command matches multiple devices.
- Keep plural or all-room wording such as `living room lights` as deliberate group control.
- Add a backend API route for setting dimmable device levels.

## v0.7.33-alpha

- Stop any current spoken response when the mic button is pressed again.
- Speak command confirmations directly, for example `Bedroom 1 Light turned on.`
- Keep numbered commands such as `livingroom light 1` targeted to the specific device instead of all room lights.
- Make heating on/off commands adjust heating setpoints only, without sending thermostat mode on/off commands to TRVs.

## v0.7.32-alpha

- Understand singular forms such as `what light is on` and `which switch is on`.
- Keep text output headed as `Lights on` or `Switches on`, but speak only the direct answer.
- Prefer room names for spoken light answers when available, for example `Bedroom 2.`

## v0.7.31-alpha

- Add a sticky floating microphone button for quick voice input on mobile dashboards.
- Add `?voice=1` voice mode URL that opens a large tap-to-speak panel for home-screen shortcuts and Samsung routines.
- Show listening/error state feedback while the browser speech recognizer is active.

## v0.7.30-alpha

- Add separate assistant speech text so audio can sound natural while dashboard output stays compact.
- Speak home temperature as degrees, humidity as percent, power as watts/kilowatts, and energy as kilowatt hours.
- Read Octopus whole-house power as natural audio, for example `Power is whole-house live power from Octopus Energy Live Meter: 319 watts.`

## v0.7.29-alpha

- Add dashboard view options for summary tiles, shortcuts, rooms, inactive rooms, no-signal rooms, devices, and output.
- Hide no-signal rooms such as Life360 by default while keeping them available from the view controls.
- Hide inactive rooms by default to keep the Rooms panel focused on active rooms.
- Tighten the mobile layout for Samsung S25 Ultra-sized browser viewing.

## v0.7.28-alpha

- Remove room-level presence chips because generic presence sensors do not reliably mean a person is in that room.
- Keep household presence in the People summary tile and room details device lists.

## v0.7.27-alpha

- Add clickable room tiles that show room explanations and the devices behind each tile.
- Add a room details API and assistant intent for explaining named rooms.
- Show a fallback "No signals" tile chip when a room has devices but no summarizable signals.

## v0.7.26-alpha

- Show room motion chips when a device is motion-capable even if its current motion value is missing.
- Show presence counts for presence-only rooms such as Life360.

## v0.7.25-alpha

- Prefer labelled Hub Info rows over raw attributes for CPU, memory, uptime, and restart values.
- Format Hub free memory, last restart, and uptime in readable units.
- Fix controllable device loading when devices have unknown/null switch state.

## v0.7.24-alpha

- Sort controllable devices with active/on devices first, then alphabetically within each state.

## v0.7.23-alpha

- Format Hub free memory in the Online status pill as MB or GB, including numeric-only Hub Info values.

## v0.7.22-alpha

- Show compact Hub health in the Online status pill.
- Color the status pill amber/red for elevated Hub CPU load or low free memory.

## v0.7.21-alpha

- Hide room motion chips when a room has no motion sensors.
- Label socket-like app/appliance/multimedia switch rooms as Sockets and keep power visible when available.
- Move Rooms above Controllable Devices and make Controllable Devices collapsible.

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
