# HomeBrainOS 0.18.117 — Preserve positive occupancy timer causality

## Live issue reproduced
0.18.116 correctly rejected the unsupported claim that an empty room
experienced ghost motion, but its final safety guard dropped the
**strongest available positive explanation** from the latest investigation.
The model had actually retrieved the three sensor histories linked to
App 4019 and the light's command/state events:

- The FP400 input (7978) was recorded active from 15:38:37.493 to
  16:58:28.633 UTC. Light 1 was ON 16:30:46.568–16:58:58.937.
  App 4019 issued OFF at 16:58:58.691, precisely 30.058s after
  the FP400 inactive edge; the light reported OFF 246ms later.
- Later Linptech Kitchen (7778) went inactive 17:00:26.835, FP400
  17:00:40.144, and Matter LWR01 (7986) 17:00:46.653. App 4019
  issued OFF at 17:01:16.922, 30.269s after LWR01's inactive edge;
  the light reported OFF 173ms later.
- Each relevant sensor's retained event metadata lists App 4019 as a
  listener; cloned Livingroom Soft Sensor (7766) does not.

This strongly supports the operating explanation that sensor-reported
activity retained the ON state, and that the OFF command followed the
last observed inactive input after roughly 30 seconds. It does NOT
establish whether the physical room was empty, whether any sensor
falsely reported occupancy, or whether every possible past event was
retained.

## Implementation
- New read-only, ID-agnostic typed-event correlation service.
  It requires actual app-produced OFF and a subsequent switch OFF
  transition within a bounded 3s delivery window. The originating app
  must be listed as an event listener of the inactive sensor.
- Correlate each OFF with the latest eligible recorded inactive
  transition within 180s; suppress an input edge contradicted by a
  subsequent recorded ACTIVE event.
- Include bounded observed active intervals when their final timestamp
  matches the sensor's inactive edge. Report measured millisecond
  deltas, not rounded natural-time estimates.
- The prior uncertainty guard now **preserves verified timing
  correlations** and does not replace a useful explanation with
  generic 'cause not verified' alone. Correctly cautious responses
  still remain cautious.
- No hardcoded room, light, app, sensor or clone names in logic.
  No Hubitat writes, no new keyword-based router.

## Testing
Synthetic replay of the exact two observed OFF sequences, input
listener mapping, cloned sensor exclusion, reactivation invalidation,
unpaired-command rejection, generic device/app IDs, API response
serialization and existing v0.18.116 claim-guard regression.

## Caution
"Last observed inactive sensor" is **bounded to returned history**.
The observed 30s timing is evidence consistent with an inactivity
delay, not independent proof of the complete internal Groovy timer
logic. Native app logs/source are needed for exhaustive runtime proof.
