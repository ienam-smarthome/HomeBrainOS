# Hubitat MCP AI 0.14.2

## Diagnostic System Check

0.14.2 improves the deterministic morning and manual System Check without adding
another AI pass.

### Device activity classification

- Requests `lastActivity` as part of the detailed device manifest when Hubitat MCP
  makes it available.
- Keeps explicit offline/unreachable states separate from activity age.
- Warns about old periodic telemetry while classifying event-driven or normally
  static devices as quiet rather than offline.
- Separately records long-active motion, long-lived normal occupancy, and devices
  with an activity field that has never supplied a usable timestamp.
- Correlates three or more stale devices from an identifiable subsystem when their
  last reports fall within the configured cluster window. A group of MQTT devices
  therefore becomes one possible MQTT interruption instead of unrelated faults.

### Log fingerprinting

- Removes timestamps, UUIDs, request/correlation/trace IDs, volatile object
  addresses, and changing long numeric IDs before grouping.
- Gives recurring MCP Rule Server / Visual Rule Builder feed warnings one stable
  semantic fingerprint.
- Records the occurrence count plus first-seen and last-seen times for each log
  group.
- Uses the app/component name as the finding title when one can be identified.

### Health hierarchy

- Reports Hub, Devices, Automations, and Logs health independently.
- Keeps the hub healthy when MCP/hub connectivity is healthy but peripheral
  devices, automations, or logs need attention.
- Orders actionable device and automation findings ahead of recurring log noise.
- Groups dashboard findings by subsystem while retaining new/resolved tracking.

The audit remains read-only. Default thresholds are 24 hours for periodic
telemetry, 15 minutes for same-subsystem clustering, and 2 hours for a motion
sensor that remains active.
