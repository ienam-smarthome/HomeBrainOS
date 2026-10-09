# 0.16.154

Room-status health failures now have deterministic precedence over retained activity state.

- A room-filter device that explicitly reports offline/unavailable/failed/timeout/disconnected or a direct connection failure is annotated with a health alert and an activity-state reliability qualifier.
- Synthesis must surface explicit health/connectivity failures prominently and cannot reduce an offline sensor to merely inactive/not present. A retained value may be shown as "offline; last reported inactive".
- Room answers containing an explicit health failure must include a Device Health/Warning section.
- Power state, sensor health, transport diagnostics and root cause remain separate evidence classes; an MQTT diagnostic is not promoted into an unverified hardware/network cause.
- Regression coverage includes the observed Seeed Studio pattern: switch=on, motion=inactive, sensorStatus=offline.

Read-only; no device-control or confirmation behavior changes. Continues #758 / #759.
