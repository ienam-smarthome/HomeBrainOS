# 0.16.161

- Add a narrow deterministic, read-only path for explicit room-status requests such as `check livingroom status and states`.
- Resolve the requested room against Hubitat's authoritative room metadata and perform one detailed, room-filtered device read. Avoid model-driven duplicate room filters.
- Preserve per-device motion, presence, temperature, humidity, illuminance, battery and switch states without conflating sources.
- Separate an explicitly offline or connecting/failing sensor from current occupancy and environmental measurements. Retained values appear only under Device health with a freshness warning; switch=on does not cancel offline status.
- Do not assume missing status attributes prove every sensor is online or invent a missing-device count.
- Add deterministic formatter and end-to-end agent-route regression tests including Seeed Studio MR60BHA2 device 7304.

Scope: this specialised route covers explicit `check/show/report <room> status [and states]` requests. Other open-ended queries may still use general model synthesis. Changes are read-only, with no device-control changes.
