# Hubitat MCP AI 0.14.8

## WebUI JavaScript hotfix

- Fix a literal `\n` sequence accidentally inserted between two JavaScript
  function declarations in the 0.14.7 WebUI.
- Restore dashboard startup so MCP/model status, live dashboard tiles, System
  Check metadata, and scheduled-check data populate normally.
- Keep the 0.14.7 colour-coded System Check findings and removal of the
  redundant `WARNING:` prefix.
- Add a regression assertion so the invalid separator cannot be reintroduced.
