# Hubitat MCP AI 0.10.239

- Makes a unique normalized exact device label outrank all fuzzy candidates.
- Keeps control requests fail-closed when multiple devices genuinely share the
  same normalized exact label.
- Adds regression coverage for exact `TV` resolution against similarly named
  devices such as Google TV blockers and unrelated fuzzy matches.
