# 0.10.433

- Replace the 0.10.432 active-room projection with two server-side capability-filtered `hub_list_devices` reads: `MotionSensor` and `Switch`.
- Request only `id`, `name`, `label`, `room`, `capabilities`, and `currentStates`, then de-duplicate by device id and apply the existing active-room definition locally.
- Keep pagination bounded per capability filter.
- If the filtered fast path fails or returns no source records, fall back to the established complete authoritative inventory so a schema/projection problem cannot be reported as a confident `No rooms are currently active` answer.
- Add regression coverage for filtered current-state reads, pagination, and zero-result fallback.
