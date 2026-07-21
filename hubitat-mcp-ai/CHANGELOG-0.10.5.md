# 0.10.5

- Keeps device-health questions on the authoritative deterministic route so Cloud
  AI cannot reinterpret quiet event timestamps as stale-device faults.
- Preserves confirmed live `healthStatus` failures while classifying old
  `lastActivity` timestamps conservatively.
- Routes `Find devices that need attention` to the deterministic attention
  collector instead of selected-device name search.
- Installs health and attention routing outside all AI wrappers, making these
  classifications terminal.
- Adds regression coverage for health-query variants and the Attention shortcut.
