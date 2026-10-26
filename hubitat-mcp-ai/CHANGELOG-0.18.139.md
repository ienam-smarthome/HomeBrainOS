# HomeBrainOS v0.18.139 — understand whole-group smart-home questions

- The V2 tester now understands **“Which lights are currently on?”** and similar explicit current light inventory questions as **set queries**, not failed individual device-name resolution.
- Reuses the existing state-aware **paginated Hubitat audit device reader** and established `is_light_device`, `device_attributes`, and `room_name` helpers. Does not require device IDs, AI planning, model tokens or any device-control operation.
- Returns matching light names, rooms and counts, plus the number of unknown switch states. Explicitly distinguishes Hubitat reported switch state from independently verified physical lighting, and warns when the device inventory is a partial fallback.
- The V2 UI displays relevant group metrics (matching lights, inventory size/coverage/pages, unknown switch state) instead of meaningless incident command-retention scores.
- Single-device diagnostics, historical investigation and normal production V1 remain unchanged. Strict token/opt-in access and read-only permission stay in place.
