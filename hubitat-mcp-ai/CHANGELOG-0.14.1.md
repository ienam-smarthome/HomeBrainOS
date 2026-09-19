# Hubitat MCP AI 0.14.1

## WebUI JavaScript hotfix

0.14.1 fixes a frontend parse error introduced in 0.14.0.

The generated dashboard script contained a literal backslash-n sequence between
the existing Refresh MCP handler and the new System Health button handler:

`};\ndocument.getElementById('runHealthAudit')...`

Because that backslash appeared in JavaScript source rather than inside a string,
the browser rejected the entire inline script before execution.

Visible symptoms were:

- the page title/version script did not run;
- MCP and Ollama remained "unknown";
- dashboard counters stayed as em dashes;
- the System Health card remained "not checked / loading"; and
- dashboard buttons had no JavaScript handlers.

The backend health-audit implementation and MCP service were not the cause.

0.14.1 replaces the literal escape with a real source newline and adds a rendered-
WebUI regression assertion that rejects the broken sequence.

No health-audit behavior, scheduling, thresholds, or mutation policy changes in
this hotfix.
