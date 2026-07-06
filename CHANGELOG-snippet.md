## v0.9.0-alpha

Performance engineering release for high Hubitat CPU / Maker API load.

### Added
- Performance Advisor endpoint: `/api/performance-advisor`.
- Natural language support for CPU / hub load / Maker API load questions.
- Runtime counters for full refreshes, skipped refreshes, detail fetches, event updates, and estimated Maker API request rate.

### Improved
- Full refreshes are now throttled with a minimum refresh gap.
- Default background refresh reduced from 30s to 120s.
- Device detail refreshes reduced from large batches to small batches.
- Manual refresh and cache clear still force a full refresh.
- Command context refreshes now reuse cache where safe instead of repeatedly hammering Maker API.

### Goal
Reduce Hubitat busy time and excessive Maker API method calls while keeping HomeBrain responsive through cached and event-driven updates.
