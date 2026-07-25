# Hubitat MCP AI 0.10.113

## Changed

- Unified all Octopus meter and period queries on one grouped deterministic reader.
- Replaced four inventory attempts with one detailed all-device discovery request.
- Removed pre-read device-cache invalidation.
- Period queries such as today, yesterday, week and month now reuse the same Octopus device family.
- Per-device detail reads are limited to displays whose inventory records do not contain a live value.

## Fixed

- Fixed `show Octopus energy today` returning no matching display devices.
- Removed the obsolete label-filter-only Octopus read path.

## Validation

- Octopus and hybrid route tests passed: 13 tests.
- Blocking release gate passed: 279 tests.
