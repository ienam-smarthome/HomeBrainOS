# Hubitat MCP AI 0.16.96

## Hub-local one-time scheduling

- One-time relative schedules now resolve `now` through the authoritative Hubitat IANA timezone before calculating a dated Rule Machine `atTime`.
- Bare one-time clock requests use the same hub-local clock when deciding whether the next occurrence is today or tomorrow.
- The fix reuses `HubTimezoneResolver`, so DST changes such as GMT/BST are handled by timezone data rather than a fixed offset.
- Non-scheduling requests do not pay for timezone lookup; a lightweight grammar pass remains the no-I/O gate.
- Recurring daily schedules keep their existing bare `HH:MM` Rule Machine triggers and do not add a timezone lookup.
- The timezone value is cached by the existing resolver.

## Accurate confirmation wording

- Successful `pauseRule` authoring is reported as **configured to pause itself after the one-time trigger executes**.
- HomeBrain no longer claims the future trigger has already fired or that the rule is already paused merely because the self-pause action was successfully added.
