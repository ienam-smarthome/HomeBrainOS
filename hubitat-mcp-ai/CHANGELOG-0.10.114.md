# Hubitat MCP AI 0.10.114

## Changed

- Added one canonical detailed-device request shape shared by power and Octopus reads.
- Prevented the two live-reading routes from drifting to different MCP cache keys.
- Removed the obsolete duplicate OctopusEnergySummary implementation.
- Retained the short live-state freshness window without increasing cache lifetime.

## Fixed

- Added support for Hubitat and custom-driver state keys such as currentValue, displayValue and unitOfMeasurement.
- Preserved HTML cleanup for Octopus energy and cost display values.
- Updated architecture and Control Focus tests for the unified Octopus reader.

## Validation

- Focused shared-snapshot and Octopus tests passed: 19 tests.
- Related power, Octopus, metric, broker and Control Focus tests passed: 55 tests.
- Blocking release gate passed: 279 tests.
