# Hubitat MCP AI 0.10.217

- Omits device IDs from spoken answers while preserving them in written text.
- Removes equals signs and Markdown control characters from speech.
- Speaks `>` as "over", expands abbreviated hour values, and separates
  camelCase state names.
- Adds natural pauses between headings and list items.
- Expands common technical labels and symbols into spoken words and selects a
  local British-English voice when available at a natural speaking pace.
