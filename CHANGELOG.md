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
