# 0.10.135

## Room climate ranking filters

- Excludes appliance, fridge and freezer sensors from room humidity and temperature rankings.
- Requires a real Hubitat room assignment before a climate reading can participate in room comparisons.
- Keeps deterministic highest and lowest climate answers grounded in verified live measurements.
- Adds regression coverage for appliance and unassigned sensor exclusions.
