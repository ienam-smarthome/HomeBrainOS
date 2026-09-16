# 0.10.432

- Add a dedicated narrow live read for `homebrain_active_rooms` that requests only `id`, `name`, `label`, `room`, `capabilities`, and current `attributes` from `hub_list_devices` instead of the complete device-record shape.
- Request up to 200 devices in the first active-room page so the observed 124-device installation can normally be answered in one gateway call; follow the gateway's pagination contract if it applies a lower cap.
- Preserve authoritative live-state evidence and the existing active-room definition (`motion=active` OR a light device with `switch=on`).
- Leave all other whole-home queries on the existing complete inventory path so the optimization is isolated to the latency case measured live in 0.10.431.
