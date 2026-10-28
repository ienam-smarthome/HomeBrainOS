# HomeBrainOS v0.18.177 — Source-first controller sensor and log evidence

## Architecture milestone

Phase 1 follow-up to the v0.18.176 golden evidence contract. The model
must not have to invent a sensor device ID or discover every follow-up
operation just to investigate why an attested controller issued a command.

## Implemented

- Project bounded, exact-key Hubitat native device selections from current
  stored controller configuration (motionSensors, keepOnSensors and other
  typed sensor selections). Only numeric device IDs from native device
  selector values survive, never arbitrary numbers from unrelated settings,
  app labels, HTML or text; credentials are excluded.
- The canonical V2 case retains these selections **only** if the retrieved
  configuration is ID-matched and belongs to an actual command-event issuer
  in the same case. They are explicitly read-time settings; they are not
  proof that identical settings were effective on the incident date.
- Extend the V2 host read-scope reviewer to allow only those source-attested
  configured sensor IDs, without allowing arbitrary model-supplied device
  IDs, custom device names or write capabilities.
- Deterministically propose up to two bounded sensor history reads after
  the existing command-issuer configuration bootstrap and before model
  planning; the normal host READ/effect/schema/ID/duplicate/budget reviewer
  still approves every read. A time-filtered incident read is used only
  when both fields are explicitly advertised and the source command has
  a valid timestamp. Otherwise the collector uses bounded hoursBack.
- Request one bounded read-only log coverage sample from the event-attested
  controller if hub_manage_logs/hub_get_logs is present in the live
  read-only manifest. Log text and private fields are deliberately dropped:
  timestamps and source availability only.
- Surface explicit stage diagnostics: controller_sensors with verified
  sensor IDs/source completeness, controller_logs with retained clock
  bounds, and restart_verified=false. A missing log page is not proof
  of a restart or of no prior command execution.
- Current sensor selections appear in compact model planning evidence
  with historical_selection_verified=false. They are source scope, not
  an inferred causal verdict.

## Safety and limitations

All work is READ-only. No Hubitat device commands, Rule Machine writes or
production Main Ask controls are changed. V2's HTTP read-only boundary
and confirmation rules remain intact. Unsupported live tool schemas,
missing selections, stale/missing command evidence and budget exhaustion
produce source-limited diagnostics and leave causal uncertainty intact.

The Oct 28 Livingroom Light 2 case can recover event-attributed app
4020's stored motion/keep-on sensor selections and attempt those sensor
event histories. Actual live Hubitat data, current sensor selections,
30-second rule timing, event-time configuration, and restart causation
remain unverified until a separate read-only live acceptance run.

## Live acceptance after installing 0.18.177

Ask the existing read-only Investigation V2 question for the latest
Livingroom Light 2 OFF transition, without changing anything.

Inspect bootstrap_diagnostics for:
- history_command_context command_records_found
- controller_config settings_projection / typed_settings_fields
- controller_sensors status / sensor_id / observed_rows
- controller_logs oldest_available_utc / newest_available_utc and
  restart_verified=false

The causal answer should identify an attested command issuer if an
unfiltered event exists and explain what the sensor histories actually
support. Current app settings alone can never prove the historic rule
branch or explain an observed delay.

The next architecture stage is a live-schema-projected native MCP tool
loop with verified host middleware and recorded transcript replays,
followed later by separate, confirmation-protected write migration.
