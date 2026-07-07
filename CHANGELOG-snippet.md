## 0.9.8-alpha - Maker API Event Parser Fix
- Fixed Hubitat Maker API event POST parsing for JSON, form-encoded, and nested body payloads.
- Correctly maps Maker API fields: `deviceId`, `name`, `value`, and `displayName`.
- Event updates now increment `state_event_version` and update the SQLite live cache.
