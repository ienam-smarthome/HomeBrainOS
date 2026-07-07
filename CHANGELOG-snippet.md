## v0.9.6-alpha - Reliable Live State Sync

- Added targeted live switch/light state refresh using Maker API device detail endpoints.
- Dashboard tiles now sync current light/switch states without waiting for full cache refresh.
- "Which lights are on" and "which switches are on" force a current-state sync before answering.
- Added GET support for `/api/state-sync` for quick browser testing.
- Added performance counters for live switch sync so Hubitat load can be reviewed.
