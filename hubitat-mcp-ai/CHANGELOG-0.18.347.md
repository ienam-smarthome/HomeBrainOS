# Hubitat MCP AI v0.18.347 — general typed-method command evidence and read-only app decision window

## Actual live result (2026-11-02, v0.18.346)
HomeBrain returned 31.047-second read-only Gemma response for main Thermostat. Main thermostat reported off/idle at 21.0°C, setpoint 12.0°C. A target-scoped 14-row history recorded a `command-setThermostatMode(off)` from app 2710 at 22:30:02.397 UTC, followed by device mode `off` at 22:30:02.791 UTC (+394ms). This is a recorded command and state association, **not** independent boiler telemetry or proof that the scheduler/protection caused it.

The response falsely treated the missing scheduler/job logs as compatible with a proven 'all rooms satisfied' cause, claimed there was no heat-engagement command, and inferred protection/early-override inactivity from idle state. The shared coverage incorrectly marked `command_history` missing because it recognized only `command-on/off` in mixed histories. A successful app config read for app 3970 did not verify current scheduler decisions. **First-answer grounding review: FAIL**, not a Claude-comparison score.

## General change (not thermostat-word patches)
- Typed successful read-only `homebrain_device_history` and `hub_list_device_events` histories can contain any explicit `type=command`, timezone-aware `command-<method>` records; those now qualify as positive command history without claiming exhaustive coverage.
- Model-facing source packet shows exact method/issued-at time and app producer only when `producedBy.type=app` and a positive numeric ID is present. It explicitly marks upstream scheduler reason, physical boiler effect and completeness unverified.
- If an application issuer is positively observed for a device uniquely named in the user question, one ±10-minute, app-ID-scoped read-only `hub_get_logs` is planned for the most recent command; no retry after a matching app-log attempt, even failed. Require live read tool schema and nonmutation effects. No new provider rounds and no new write privileges. The log contents may still be empty/unavailable; no inferred decision.
- Technical JSON exposes `observedMethodCommandEvidence` without unbounded raw app logs or credentials.

## Safety, validation and limits
Use anonymous synthetic fixtures for wrong identity, untyped command, unverified issuer, bad clock, positive method command, duplicated log attempt and unrelated questions. Full exact-head CI and container smoke required before merge. **No Hubitat/HA changes.** This is evidence-selection/consistency, not the final single-planner rewrite and not semantic proof of every model-authored clause. Next first-shot test belongs to a different domain (bathroom fan FanBoost/manual/schedule/humidity), rather than repeating the same thermostat or MQTT case. The quality targets remain NOT MEASURED.
