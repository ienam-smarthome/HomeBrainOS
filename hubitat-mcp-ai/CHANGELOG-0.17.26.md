# HomeBrain 0.17.26 — Mobile Historical Journal and app-log diagnostics

- Adds a responsive **Historical Journal** panel to the existing HomeBrain web and Home Assistant ingress UI. It displays event/log socket connectivity, persisted event and app-log counts, database size, storage errors, last event reception time, and recorded/open connection gaps.
- Expanded panel reveals first/last stored timestamps, retention settings, recent gap details, a bounded list of the newest 12 **device events only**, and per-allowlisted app log counts. A manual refresh works on Android without a PC.
- New bounded `GET /api/evidence-journal/recent?limit=12` endpoint omits app-log message content. It is read-only and does not cause hub device reads.
- Enhances `/api/evidence-journal/status` and the existing `/api/status` journal summary with `db_bytes`, `event_rows`, `app_log_rows`, `tracked_app_ids`, `captured_app_log_counts`, `open_gaps` and `recent_gaps`.
- A reconnected journal socket clears its stale *transport* warning when all enabled streams are healthy, without clearing storage or dropped-row warnings.
- Regression tests cover app 4015 log count persistence across restarts, application-log exclusion from recent-device results, gaps, timestamps and mobile panel elements.
- **Historical evidence caveats remain:** connection does not establish app execution, zero log rows does not prove the app did not run, and collector-received timestamps are not independently verified event times. The journal never claims complete history or inactivity from missing records.
- Existing installation settings remain unchanged. The journal is opt-in, and no Hubitat rules or device controls are modified by this release.

**Live test:** After updating HomeBrain to 0.17.26, open the Historical Journal panel in the Home Assistant app. Confirm the counters reflect previously collected events across restart, inspect gap details, and check whether app 4015 logs accumulate following ordinary user-controlled device activity. A zero log count is a diagnostic unknown, not a failure proof.
