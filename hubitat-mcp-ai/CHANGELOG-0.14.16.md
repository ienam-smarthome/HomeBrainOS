# Hubitat MCP AI 0.14.16

## Complete coloured Pushover reports

- Fix coloured System Check notifications being cut off after the device / low
  battery sections.
- Keep the red offline-device and amber low-battery highlighting introduced in
  0.14.15.
- Split an oversized System Check into numbered Pushover messages instead of
  truncating the later sections.
- Preserve Automations, Logs, Other findings, and Resolved findings across
  message parts.
- Keep every individual Pushover message within the 1024-character API limit.
- Split only at complete lines so HTML colour tags are never cut in half.
- Avoid leaving a section heading stranded at the end of a message where
  possible.
- Return the number of Pushover messages sent to the manual System Check action
  so the dashboard can confirm multipart delivery.
