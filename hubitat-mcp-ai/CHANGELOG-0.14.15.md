# Hubitat MCP AI 0.14.15

## Targeted Pushover device-state colours

- Enable Pushover HTML rendering for System Check reports.
- Colour only the important device fields, matching the calmer WebUI treatment:
  - unavailable/offline device names and their state are red;
  - low-battery device names and the reported battery value are amber.
- Keep section labels, thresholds, totals, automation names, log text, and other
  surrounding content neutral.
- Escape dynamic message content before enabling HTML so device/log names cannot
  accidentally be interpreted as markup.
- Replace raw character slicing with complete-line truncation so the 1024
  character limit cannot cut a colour tag in half.
- Preserve the existing named-device Pushover report, scheduled delivery, and
  manual **Send report to Pushover** behavior.
