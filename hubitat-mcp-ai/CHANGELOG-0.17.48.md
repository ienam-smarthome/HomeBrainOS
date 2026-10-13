# HomeBrain 0.17.48 — Event-age-aware native history and evidence-owned reporting

## Live failure driving this release

The 0.17.47 live query ran at 2026-10-13 22:52 UTC against a requested focal event at **2026-10-12 22:49:27 UTC**, **24 hours and three minutes earlier**. Native light/button/command history was queried with default `hoursBack: 24`, thereby excluding the focal source events previously seen nine minutes earlier. The latest response then said app 1251's command could not be verified, promoted journal collector-received button time into a physical timestamp, and failed to disclose the 24-hour history cutoff.

## Architectural improvements

1. **Age-derived bounded native history:** For a user-specified complete BST/GMT dated clock, independently resolve the UTC anchor before any native history read. Set a single longer `hours_back` for light state, command provenance and physical button source, using existing absolute-time DST-safe arithmetic, up to 168 hours. At the observed live age, the request becomes **26 hours**, including a one-hour margin. Avoid a second exploratory round.
2. **Coverage contracts:** Report requested historical scope and whether the fixed 24-hour default omitted the focal instant. If the expanded query also omits it, the result remains **not returned / upstream retention unknown**, never 'no event happened'. Beyond 168 hours, report the explicit cap.
3. **Source-typed final reconstruction:** When every relevant source class has been read, derive the chronology from native observations, independently retained command rows and journal collector receipts, without relying on a free-form model to establish core timestamps and provenance. Separate current 300-minute configuration, missing app logs, sensor eligibility and journal capture gaps.
4. **Budget:** One-pass finalisation metric `lockout_focal_evidence_report`. If required reads fail or further independent tasks are requested, retain existing investigative fallback rather than incorrectly claiming completeness.
5. **Tests:** Regress native 24-hour cutoff, 26-hour lookback, future/mislabelled UK clocks, 168-hour cap, native command recovery, persistent upstream source omission after expanded reads, and safe synthesis without upgrading journal timestamps.

The read-only patch changes HomeBrain's investigation and explanation. It does not change Hubitat devices, rules, lockout durations or actual automation execution.

## Limitations

A 26-hour query only requests older source rows. It cannot recover events that Hubitat or its MCP server has already permanently discarded; the Historical Journal retains separately labelled collector-received observations. If native command rows remain unavailable, HomeBrain must state that the command cannot be established **from this request** while acknowledging the exact source/time coverage boundary.
