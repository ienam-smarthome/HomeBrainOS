# Hubitat MCP AI 0.10.195

## Repair MCP invalidation and add grounded routing safeguards

- Fixes the indexed state broker's stale invalidation override so uncached MCP
  reads no longer raise a positional-argument `TypeError`.
- Adds an outer AI grounding guard that withholds device claims absent from the
  supplied MCP evidence and reports its trigger rate at `/api/ai-grounding`.
- Adds a single four-tier catalogue interpreter in passive shadow mode and
  attaches final router, intent, agent, capability and confidence metadata to
  the answer's technical routing trace.
- Adds fixed routing evals for control, deterministic reads, diagnostics, and
  open-ended requests.
