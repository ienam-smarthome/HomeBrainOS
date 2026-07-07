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
