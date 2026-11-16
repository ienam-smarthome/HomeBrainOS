# User-facing dates and timestamps (UK presentation)

The hub and connected MCP sources can return ISO 8601 times, often with an
explicit UTC offset. Keep the **original timestamp, UTC offset, fractional
seconds, source identity and chronology** intact in the underlying evidence.
Do not rewrite or convert tool arguments, returned receipts, Technical JSON,
debug logs, source query bounds or quoted code/data examples.

In **natural-language answers intended for the user**, prefer a familiar
named weekday/day/month and **12-hour** clock with am/pm, e.g.
**Sunday 15 November 2026 at 9:48 pm GMT**, rather than
`2026-11-15T21:48:21.024+0000`. For ordinary prose, minute precision is
usually enough; keep original exact instants in the source receipts and
Technical JSON. When two competing events occur in the same minute or
seconds/milliseconds are necessary to explain ordering, include that
precision *in readable local time* (e.g. **9:48:21.024 pm GMT**) and
never silently change their sequence.

Convert explicitly offset-aware timestamps to the **configured hub IANA
timezone** (normally `Europe/London`), showing **GMT** in winter or
**BST** in summer when that is the configured zone. For example,
`2026-07-10T08:10:10+0000` is **Friday 10 July 2026 at 9:10 am BST**,
not 8:10 am London time. The configured zone is a presentation setting,
not independent verification of the hub's clock. Shorter dates are fine
when day and timezone are already clear.

If the source only supplies an ambiguous local clock time or a date without
an offset/time-zone contract, do **not** guess the zone or silently convert it
to London time. State the source clock or that the time zone is unspecified.
Prefer named months to avoid ambiguity between UK day/month and US month/day.
If the user asks for an original timestamp or machine-readable ISO, give it
unchanged alongside any optional readable display.

This is presentation guidance, **not** a causal inference, missing-history
fix, new source requirement, automatic reread, device-specific prompt or
evidence transformer. Read-only chronology and source coverage must remain
honest and exact.
