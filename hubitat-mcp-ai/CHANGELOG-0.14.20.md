# Hubitat MCP AI 0.14.20

## Deterministic room measurement reads

- Fix a live 0.14.19 inconsistency where the same terse request,
  **bathroom temperature**, produced different results from mobile and PC.
- Accept shorthand current-state phrases such as `bathroom temperature` and
  `Bedroom 1 humidity` without requiring a leading "what is" / "show me".
- Read the requested live attribute first and match capable reporters using both
  device label and room metadata.
- If exactly one matching reporter exists, answer directly without calling the
  language model or first attempting a literal device-name resolution.
- Preserve clarification when multiple capable reporters match.
- Fall back to targeted device resolution only when no capable reporter matches,
  preserving generic `value` / `valueStr` devices and precise missing-attribute
  responses.
- Avoid leaving a successful answer marked **Unresolved** merely because an
  earlier speculative device-name lookup failed.
- Add regression coverage for the live Bathroom Meter case and room-metadata
  matching.
