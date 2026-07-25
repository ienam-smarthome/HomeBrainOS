# Hubitat MCP AI 0.10.112

## Changed

- Current-power summaries now use the proven all-device detailed attributes response first.
- Removed unnecessary capability-filtered and compact-summary attempts from the successful power path.
- Other live metrics continue to use the shared summary snapshot and compatibility fallbacks.
- Shared-summary regression coverage now uses humidity, while power has dedicated direct-evidence tests.

## Validation

- Focused power, shared-snapshot and observability tests passed: 9 tests.
- Power, metric, device-index and state-broker tests passed: 33 tests.
- Blocking release gate passed: 279 tests.
