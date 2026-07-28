# Hubitat MCP AI 0.10.194

## Route natural log-purpose queries to Hubitat logs

- Recognizes natural requests such as `Check logs to see if there are any
  issues`.
- Supports equivalent `check whether`, `find`, and `and see` purpose clauses
  for issues, errors, and warnings.
- Routes those requests to the deterministic 24-hour Hubitat log scan using
  separate server-side error and warning filters.
- Keeps explicit HomeBrain, assistant, and request diagnostics on their
  separate bounded request-trace route.
