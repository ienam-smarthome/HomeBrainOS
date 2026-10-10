# 0.16.157

- Exclude explicitly offline sensors from current active/inactive room occupancy classifications.
- Do not include potentially stale illuminance, temperature, or humidity readings from offline sensors in current room ranges.
- Require room summaries to avoid contradictions between Device Health and Occupancy/Environment sections.

Follow-up to #763. No device-control changes. Pending complete CI validation and live verification.
