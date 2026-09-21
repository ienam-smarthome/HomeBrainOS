# Hubitat MCP AI 0.14.17

## Complete Pushover System Check parity

- Keep the multipart Pushover delivery introduced in 0.14.16.
- Add a dedicated **Device warnings** section for device findings that are not
  offline/unavailable or low-battery items, such as stale telemetry and motion
  active too long.
- Include the actual **New since previous check** item names instead of showing
  only the numeric `new_count` summary.
- Keep **Resolved** findings when present.
- Preserve targeted colours: offline device names/states remain red and
  low-battery device names/values remain amber.
- Preserve all later sections across numbered Pushover message parts.
