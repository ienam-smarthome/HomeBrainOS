## 1.5.0-alpha - Natural Intelligence Sprint 1

- Added natural formatter and Sprint 1 endpoint improvements.

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

- Added deterministic intelligence for questions like why are 3 lights on.
