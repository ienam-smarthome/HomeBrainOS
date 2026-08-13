# 0.10.427

## Why this release

Direct follow-up to 0.10.426. After applying that release, the user
re-ran "When did the front door last open?" and it still answered "No
contact events were reported for Front Door in the last 168 hours" -- the
window-widening fix was necessary but not sufficient. Live testing directly
against the user's real Hubitat hub (via a separate live MCP connection,
not the patched app) isolated the actual cause: the upstream
`hub_list_device_events` tool's own `attribute` filter is unreliable.
Calling it with `attribute="contact"` for the real Front Door device
(`deviceId 7399`) returned zero events, while an identical call with no
attribute filter at all, over the same window, showed several real contact
events. Calling it with `attribute="motion"` on that exact same device,
same window, filtered correctly. The failure is entirely silent -- no
error, no `is_error` flag, just a clean empty list -- so it is
indistinguishable from "no events occurred" unless the caller stops
trusting the filter and verifies independently, which is exactly what this
live test did.

## Fixed

**The upstream per-attribute event filter silently dropped real contact
events.** `DeviceHistoryService.history()` previously forwarded the
caller's `attribute` straight through to `hub_list_device_events` as a
server-side filter. That filter cannot be trusted for every attribute name
-- confirmed live to work for `motion` but fail for `contact` on the same
device -- and a caller has no way to tell a genuinely-empty result from a
silently-broken filter, because both look identical.

The host no longer forwards `attribute` to the upstream call at all. It
always fetches the widest bounded, unfiltered window (up to the maximum
limit of 50 whenever a single attribute is requested) and filters by
attribute name locally, then applies the caller's originally-requested
`limit` after filtering. A broken upstream filter for any attribute -- past,
present, or a new one introduced later -- can no longer produce a false "no
events" answer, because this code never depends on the upstream filter
being honoured in the first place.

## Validation

- `python -m pytest -q` -- 880 passed. New coverage in
  `tests/test_device_history_service.py`:
  `test_attribute_filter_is_applied_locally_not_forwarded_upstream`
  reproduces the exact live-confirmed upstream failure shape (a mock that
  silently returns zero events only when `attribute="contact"` is
  forwarded, mirroring the real hub's observed behavior) and asserts the
  attribute filter is never forwarded upstream;
  `test_client_side_attribute_filter_still_respects_requested_limit` pins
  that the client-side fallback still honours the caller's `limit` after
  filtering. `test_reads_bounded_authoritative_history_after_targeted_resolution`
  and `test_attribute_scoped_query_widens_default_window_to_seven_days`
  (from 0.10.426) were updated to match the new upstream call shape (no
  `attribute` key, fetch capped at 50). Confirmed both new tests fail
  against the pre-fix code (`count` came back `0` instead of `1`, exactly
  reproducing the live bug) before restoring the fix.
- Live-verified directly against the user's real Hubitat hub: re-ran
  `hub_list_device_events` for the Front Door device with
  `attribute="contact"` (0 events, confirmed broken), with no attribute
  filter (real contact events present), and with `attribute="motion"`
  (filtered correctly) -- isolating the failure to the upstream filter
  itself, not device resolution, windowing, or event-shape mapping.
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.427
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
