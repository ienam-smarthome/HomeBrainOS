## v0.9.7-alpha - Event-driven state engine

- Removed automatic dashboard/live-question Maker API detail refresh loops.
- Dashboard and AI answers use the shared event/cache state by default.
- Added explicit live-sync controls and safer default refresh intervals.
- Manual `/api/state-sync` remains available for resync.
