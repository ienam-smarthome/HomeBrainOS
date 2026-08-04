# Hubitat MCP AI 0.10.325

## Changed

- Added deterministic contact-history follow-ups using the previously returned event timestamp.
- Added calendar-day aggregation for questions such as “How many times did the front door open yesterday?”.
- Added filtered natural-language contact-event lists for yesterday.
- Removed generic causation disclaimers from ordinary filtered history lists.

## Safety

- Event calculations remain bounded to authoritative Hubitat contact history.
- Follow-ups are scoped to the current browser session.
- No change to device control, confirmation, grounding, or transport behaviour.
