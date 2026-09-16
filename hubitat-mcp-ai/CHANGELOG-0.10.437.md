# Hubitat MCP AI 0.10.437

## Changed

- Whole-home snapshots now read their common live state from the complete `hubitat://context` resource when available, covering presence, motion, switches, contacts, locks, and batteries in one bulk snapshot instead of forcing a full `hub_list_devices {}` read.
- Home presence now distinguishes person/tracker presence from physical occupancy devices using capabilities, so a motion/occupancy sensor that also exposes `presence` is not listed under people at home.
- Health/attention coverage is explicit. The bulk context resource does not contain `healthStatus`, `networkStatus`, `rtt`, or `hubAlerts`, so context-backed home snapshots return `alerts_complete: false` rather than turning missing health fields into a false zero-alert claim.
- If the bulk context resource is unavailable, partial, truncated, or identity-incomplete, the established complete-inventory fallback remains authoritative and preserves the existing exhaustive health-alert scan.

## Why

Live 0.10.436 testing showed `What's happening at home?` still spending about 24.5 seconds in MCP HTTP because the home snapshot always called the unprojected 124-device inventory. The same installation already answers active-room, light, and motion questions from `hubitat://context` in roughly the one-to-three-second range. This release moves the shared whole-home state plane onto that existing structural resource without adding prompt keywords or weakening completeness checks.

## Validation

- Added a regression test proving a complete context snapshot does not call the full device inventory.
- Added a regression test proving physical motion/presence sensors are excluded from the people-at-home list while remaining visible as active motion.
- Added fallback coverage proving rich health alerts remain complete when the full-inventory path is used.
