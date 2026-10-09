# 0.16.153

Room-status evidence is now more complete and provenance-preserving.

- Room filters retain relevant per-device state values (including switch/level, motion/presence, temperature, humidity, illuminance, battery and explicit status fields) instead of returning only the matched room value.
- Source-supplied activity/update timestamps are preserved as observations; they are not promoted into freshness or failure claims.
- Final synthesis is instructed to keep individual sensor provenance, avoid unattributed ranges, distinguish cached active/present state from fresh detection, and keep power/status/transport diagnostics separate from unverified root cause.
- Inventory count differences cannot be promoted into a missing-device claim without comparable scopes and a concrete missing numeric ID.
- Out-of-room sensor data must be clearly labelled as contextual.
- Regression tests cover room-state/timestamp projection, compact non-room filters, and the room-status synthesis policy.

All changes are read-only and do not alter device-control or confirmation behaviour. Tracks #758.
