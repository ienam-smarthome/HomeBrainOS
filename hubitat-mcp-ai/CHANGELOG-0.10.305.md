# Hubitat MCP AI 0.10.305

- Record `device_resolution_ambiguous` at the resolver's explicit fail-closed ambiguity decisions.
- Count duplicate exact labels and unresolved ranked ties.
- Do not count no-match, low-confidence single-candidate, or successful unique resolutions.
- Keep metric collection request-local and privacy-safe.
- Add focused resolver metric regression tests.
