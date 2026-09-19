# Hubitat MCP AI 0.14.9

## Targeted System Check colouring

- Keep System Check finding rows predominantly neutral for easier scanning.
- In the Devices section, colour only the device name and its state/value.
- Use red for unavailable/offline device names and states.
- Use amber for low-battery device names and the reported battery value.
- Keep prefixes, thresholds, descriptive text, automation findings, and log
  findings neutral.
- Preserve the compact System Check header, Pushover report formatting, and
  removal of the redundant `WARNING:` prefix.
