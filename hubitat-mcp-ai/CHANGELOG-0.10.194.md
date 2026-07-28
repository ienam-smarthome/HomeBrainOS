# Hubitat MCP AI 0.10.194

## Repair log diagnostics and add grounded routing safeguards

- Recognizes natural requests such as `Check logs to see if there are any
  issues`.
- Supports equivalent `check whether`, `find`, and `and see` purpose clauses
  for issues, errors, and warnings.
- Routes those requests to the deterministic 24-hour Hubitat log scan using
  separate server-side error and warning filters.
- Keeps explicit HomeBrain, assistant, and request diagnostics on their
  separate bounded request-trace route.
- Fixes the indexed state broker's stale invalidation override so uncached MCP
  reads no longer raise a positional-argument `TypeError`.
- Adds an outer AI grounding guard that withholds device claims absent from the
  supplied MCP evidence and reports its trigger rate at `/api/ai-grounding`.
- Adds a single four-tier catalogue interpreter in passive shadow mode and
  attaches final router, intent, agent, capability and confidence metadata to
  the answer's technical routing trace.
