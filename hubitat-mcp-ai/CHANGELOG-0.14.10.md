# Hubitat MCP AI 0.14.10

## Query-first mobile layout and broken-state emphasis

- Move the Ask/Speak/answer card directly below the page heading so it is
  immediately accessible without scrolling past dashboard and System Check cards.
- Preserve the existing status pills, dashboard tiles, System Check, and shortcuts
  below the primary interaction card.
- Keep automation findings neutral while highlighting the explicit `BROKEN`
  state in red.
- Preserve targeted device colouring: unavailable/offline device names and states
  remain red, while low-battery device names and values remain amber.
- Add regression coverage for the new card order and broken-state renderer.
