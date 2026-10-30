# v0.18.244 — Automatic Historical Journal recovery for original HomeBrain investigations

## Motivation: 30 Oct Bathroom comparison

Original HomeBrain v0.18.243 knew that Bathroom Lights 1 (7818) and 2
(7821) had OFF commands and brightness observations but no switch ON/OFF
observations in the bounded native Hubitat event pages. Its subsequent
newest-N switch reads returned around 11:00, not the 02:00–07:30
incident. Historical Journal was enabled and contained thousands of
observations, but the group investigation never read it. The UI exposed
the correct read-only API only as a relative path, which cannot be pasted
as a standalone URL without the add-on host or Home Assistant ingress path.

## Original-agent implementation

- Add `group_journal_recovery.py`: one bounded, automatic, read-only
  Journal query per independently name-verified target with missing
  incident switch-state evidence, maximum 5 targets. Require an explicit
  date and independently verified hub timezone or user-provided UTC/GMT.
  Preserve the precise requested clock window rather than fetching most
  recent history; do not derive an arbitrary time from local clocks.
- Run after model investigation and before the original HomeBrain
  final evidence reconciliation, including early answer paths. A Journal
  query cannot mutate the hub or expose an unverified device ID.
- Keep journal results as a **separate source class**. A source-timestamped
  switch observation remains distinct from one whose only timestamp is
  **collector reception**; neither proves which upstream controller
  initiated an event. An empty Journal result, socket gap, or truncated
  page does not prove no activity or complete historical coverage.
- Publish a single source-ranked incident ledger containing verified
  Hubitat issued commands/levels and any archived switch observations.
  The original assistant remains model-led; there is no new V2 test
  interface and no tool write permission.
- Extend the existing journal dashboard record browser with local
  From/To time controls and a copyable **fully qualified API URL** built
  using the current browser origin and ingress-aware API path. Works
  both for direct add-on hostnames and installed Home Assistant ingress.

## UI and operational guidance

In **Browse historical records**, set device ID 7818, local date
30/10/2026, start 02:00, end 07:30 and event type Switch. Click
Search records or Copy API URL. Repeat for 7821/7807. The raw path
`/api/evidence-journal/events?...` alone is not a complete URL and
may omit the required Home Assistant ingress prefix.

The dashboard may show collected reception-only events and disconnected
stream gaps; do not infer that the device was idle when a search returns
zero. App log archive capture remains explicitly opt-in and allowlisted,
independent from the device event journal.

## Validation

Test a live-style 30 Oct multi-target receipt case, source-timestamped
and collector-received journal data, explicit time-window filtering,
empty sources, journal gaps, duplicate query prevention, unverified
target/timezone refusal, read-only original-agent response and UI link
generation. Run full Python tests, repository metadata validation and
add-on container smoke. Deployment and actual Hubitat journal contents
require user verification after installation.
