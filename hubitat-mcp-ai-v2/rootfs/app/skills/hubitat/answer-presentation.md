# User-facing dates and timestamps (UK presentation)

The hub and connected MCP sources can return ISO 8601 times, often with an
explicit UTC offset. Keep the **original timestamp, UTC offset, fractional
seconds, source identity and chronology** intact in the underlying evidence.
Do not rewrite or convert tool arguments, returned receipts, Technical JSON,
debug logs, source query bounds or quoted code/data examples.

In **natural-language answers intended for the user**, prefer a readable,
unambiguous UK date with 24-hour time: for example, **18 Feb 2026,
14:05:06.123 GMT** rather than `2026-02-18T14:05:06.123+0000`.
Interpret *explicitly offset-aware* timestamps in `Europe/London` and
show **GMT** in winter or **BST** in summer, respecting UK daylight saving.
A source stamp such as `2026-07-10T08:10:10+0000` should display as
**10 Jul 2026, 09:10:10 BST**, not 08:10 London time. Retain milliseconds
where the original event has them, especially for command-versus-state order.
Shorter natural dates are fine when the day and time zone are already clear.

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
