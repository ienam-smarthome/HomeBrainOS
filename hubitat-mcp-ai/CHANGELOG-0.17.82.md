# 0.17.82 — Historical Journal browser and focal-date protection

## Historical Journal browser
- Open **Historical Journal → Browse historical records** to query retained events by exact device ID, local day and attribute (including switch, on/off command, motion and button).
- Event rows are displayed in a horizontally scrollable, mobile-friendly table with the value, stored source classification, and a clear distinction between hub source timestamps and collector-reception timestamps.
- Results are read-only, capped at 50 records per page, and provide **Previous**/**Next** pagination through the existing exact-scope journal API.
- Pagination adds a bounded `offset` parameter and `has_more`/`next_offset` metadata; query responses still disclose partial coverage, gaps, and truncation. Saved journal rows and retention settings are unchanged.
- Event labels/data are assigned using `textContent` rather than HTML injection. App-log message bodies are deliberately not displayed in the browser.
- Because SQLite records can be retained/purged while browsing, offset pagination is a best-effort snapshot, not a guarantee of no repeats/missing rows across live changes.

## Incident date isolation
- A historical command on a different calendar day must never supply a focal day's UTC offset or be used to open an exact-time follow-up query. This is critical across DST changes.
- Unit regression: a 14 October command does not qualify as evidence of the requested 15 October event; the equivalent 14 October request still resolves.
- This change protects evidence source selection but does not itself prove an initiating actor or add a new reasoning model.

## Safety and validation
- No device actions, app/rule changes, new Hubitat polling, stored schema migration or secrets exposure.
- CI and live Home Assistant add-on verification required. Journal events remain incomplete observational evidence; an empty result is not proof of inactivity.
