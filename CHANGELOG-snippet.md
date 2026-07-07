## v0.9.4-alpha - Version Sync & Frontend Cache Fix

### Fixed
- Synchronised the backend APP_VERSION with the Home Assistant add-on version.
- Added `/api/version` as a lightweight single source for version checks.
- Updated the Web UI to display the exact backend version including `-alpha`.
- Added no-cache headers for `/` so the HomeBrain UI is less likely to show an old release after add-on updates.

### Why
- Home Assistant showed `0.9.3-alpha` while the Web UI still showed `v0.9.2` because the backend APP_VERSION was stale and the UI only read that backend value.

