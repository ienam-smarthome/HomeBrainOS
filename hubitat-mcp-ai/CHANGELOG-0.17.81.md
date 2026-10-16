# 0.17.81 — Journal query coverage and investigation foundation

- Historical Journal bounded event queries fetch one extra SQLite row to identify capped results and return `truncated` and `limit` alongside the existing `count`, `gaps` and explicitly incomplete `coverage_complete: false`. The returned event count is still capped at the existing maximum, with no additional Hubitat polling or writes.
- Add an isolated regression test for capped, exact-size and empty query results. A nontruncated response **does not** imply continuous collection.
- Add the reusable `skills/hubitat-investigator/SKILL.md` methodology and historical-journal audit document. These are developer-facing resources and are **not yet runtime-loaded**, and do not introduce an independent model loop or grant access to new data sources.

**Safety:** No changes to Hubitat devices, rules, journal retention, stored data schema, capture settings or opt-in defaults. GitHub CI and actual Home Assistant deployment verification are required before calling this release installed or fully validated.

**After upgrading:** Check journal socket connectivity and newest event, confirm rows advance, view gaps/dropped count, and run a bounded read-only incident query. The response's `truncated` value now distinguishes result-cap truncation from other inherent coverage gaps. A full investigator workflow still requires runtime integration in a subsequent release.
