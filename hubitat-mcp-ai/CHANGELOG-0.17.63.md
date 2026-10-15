# HomeBrain v0.17.63 — Unified device event evidence and historical sensor windows

## Evidence-first device health diagnostics

- Normalize direct, successful, ID-scoped `hub_list_device_events` event
  receipts independently of `homebrain_device_history` summaries.
- Preserve both outgoing command invocations and Hubitat-recorded state /
  attribute events in the same bounded result, including a history with
  15 commands and one older `mqttStatus: connected` record.
- Keep query lookback, target device ID, last returned state-event timestamp,
  producer identity, explicit event-page truncation, and command counts in
  `investigation_coverage.normalizedDeviceHistory`.
- For a supported `device_telemetry` investigation, render a source-derived
  activity / conclusion summary rather than reusing unsupported model prose
  about being physically unresponsive, one-way MQTT traffic, or precise
  current telemetry age.
- Treat device-attributed Hubitat attributes as state *events*, not proof
  of a fresh physical transport message. Outgoing command calls do not prove
  acknowledgement or failure. General/app-name filtered logs do not count
  as a direct device-ID-scoped log query.
- Record `typed_device_history_projections` for diagnostics in which this
  additional final-answer verification activated.

## Time-scoped historical causal investigation

- For an explicitly named historical ON boundary, attempt up to two
  source-verified absolute sensor-window probes before using newer-N
  device history pages.
- A source must echo the specific absolute `since`, `until` and target
  device ID to be treated as a verified historical window. A server that
  ignores window parameters must not fabricate earlier motion/presence.
- Limit subsequent cross-room adaptive exploration when a focused historical
  probe established an unresolved source-window gap. This reduces futile
  recent-event fan-out while making insufficient historical coverage visible.
- Retain existing support for untimed historical causal queries, requested
  OFF event handling and optional journal-first OFF recovery.

## Safety and limitations

All changes are read-only and do not alter Hubitat apps, rules or devices.
This release cannot verify physical MQTT/Zigbee reachability or restore
events that are no longer retained by the upstream source. The bounded
source-derived summary prioritises correctness over speculative root-cause
claims, and more specialized source reads may still be necessary.

`general_task_engine_enabled` remains opt-in by default. CI regression
tests cover 15 command events + one historical state event, rejected
cross-device evidence, and a historical ON window when the MCP server
does not prove its time filters.
