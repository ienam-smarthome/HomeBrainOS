# HomeBrainOS 0.18.446 — Hub-local historical time and capped-page coverage

## Motivation

Two live read-only acceptance traces on the installed v0.18.445 add-on:
- Bathroom Meter humidity: first successful source-real recorded-interval answer
  from a verified history read. First-attempt provenance, complete retention
  and earlier historical coverage still not independently proved.
- Bedroom 1 TRV temperature: the answer presented UTC timestamps instead of
  verified hub-local GMT/BST, called the 50 fetched mixed events "total events",
  and inferred constant temperature from three identical returned readings.
  Its evidence explicitly reported only three temperature observations in a
  50-row newest-first page, NOT proof of a 24-hour continuous series.

## Reusable implementation

- The model-planned read-only device-history host path supplies private
  flags to request authoritative `hub_get_info.timeZone` and source
  continuation, without extending user/model tool privileges.
- Verified IANA zone controls `displayTime` for event samples while raw
  source timestamps stay intact for calculations. `Europe/London`
  automatically shows GMT in winter and BST in summer. If source timezone
  cannot be verified, no UK-local display label is invented.
- When an unfiltered attribute-history page saturates its 50-event
  limit, continue backwards with native read-only `until` bookmarks,
  each one strictly before the previous oldest observed timestamp.
  Stop on the requested time boundary, short page, non-advancing bookmark,
  unavailable source or 1000-row operational memory budget. Attribute
  upstream filters are not used to fake coverage; some driver filters
  have silently returned false-empty results.
- Provide small source-qualified `sampleBounds` before verbose rows,
  plus `sourcePagesFetched`, `sourceFirstPageAtLimit`,
  `sourceWindowBoundaryReached`, `sourceCoverageStopReason`,
  `timeZone` and `timeZoneSource`. Source row totals describe only
  fetched rows. Source integrity/retention stays unverified unless an
  independent authority establishes completeness.
- Generic history prompt policy forbids interpreting sparse or identical
  samples as proof of uninterrupted physical stability or attributing
  missing reports to device/network failures without discriminating facts.
- Technical read receipts preserve timestamp labels and paging metadata
  without exposing credentials, private history outside the bounded
  observed event sample, or host-only execution hints.

## Scope and verification

Synthetic tests cover capped mixed pages with older attribute records,
bad/ignored bookmarks, short retained pages, GMT/BST conversion, missing
hub timezone and host-only hint boundaries. Existing regression suites
and release assurance must pass before merging.

No Hubitat, Home Assistant, router, installed add-on, physical device,
paid provider or external record was modified. Tests do not establish
source-real behaviour of the upstream `until` filter on the user's
installed MCP version; verify in one fresh read-only history request
after upgrading. No claim of 24-hour complete retention or an exact
physical threshold crossing is implied.
