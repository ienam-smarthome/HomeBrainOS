# Hubitat MCP AI 0.10.448

- Keep analytical attribute-history reads on the normal 24-hour default when the caller does not provide a time window, instead of widening every attribute-scoped request to seven days.
- Preserve the seven-day fallback for true point lookups by recognising the existing explicit small-limit (1-3 event) contract used by “when was it last on/open/etc.” questions.
- Prevent unrelated older boundary events from turning a complete overnight duration calculation into an unnecessary “at least” lower-bound answer.
- Reduce history-query scope for common analytical questions, lowering the amount of Hubitat event data fetched and passed into the second reasoning round.
- Add regression coverage for analytical defaults, point-lookups, and explicit hour-window overrides.
