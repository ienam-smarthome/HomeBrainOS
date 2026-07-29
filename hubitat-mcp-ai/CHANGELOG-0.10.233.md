# Hubitat MCP AI 0.10.233

- Falls back to the short-TTL device identity manifest when Hubitat's literal
  label filter returns no suitable control target.
- Applies speech-safe, confidence-gated resolution to fallback candidates so
  phrases such as `living room light two` resolve to `Livingroom Light 2`.
- Preserves fail-closed behavior for ambiguous or low-confidence matches.
- Adds a regression test covering an empty literal-filter result followed by a
  successful normalized device match and command.
