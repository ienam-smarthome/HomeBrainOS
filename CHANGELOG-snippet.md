## v0.9.3-alpha - AI Device Intelligence & False Positive Reduction

### Added
- AI Device Intelligence profiles for thermostats/TRVs, energy meters, lights, smart plugs, contact sensors, motion sensors, presence sensors, climate sensors, and battery sensors.
- `/api/device-intelligence` for classification output, confidence scores, dashboard groups, suggested rooms, and ignored checks.
- Auto-exclusion list showing devices deliberately ignored for invalid switch-state checks.

### Improved
- TRVs are no longer treated as broken switches when they expose on/off commands without a switch state.
- Octopus/energy meter style devices are classified as read-only energy meters instead of controllable switches.
- Device Inspector now separates genuine switch issues from expected non-switch devices.
- Unknown room items now include intelligence metadata and stronger suggested-room confidence.

### Practical impact
- Reduces false positives in housekeeping and AI answers.
- Leaves real issues such as smart sockets with missing switch state visible for investigation.
- Provides a stronger foundation for learning mode and one-click device mapping later.

