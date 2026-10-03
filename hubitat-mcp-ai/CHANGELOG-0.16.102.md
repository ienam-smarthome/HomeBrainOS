# Hubitat MCP AI 0.16.102

## Persistent one-time cleanup history

- Persists the latest one-time cleanup result under `/data/homebrain-one-time-rule-cleanup.json`.
- Restores last run, trigger, scanned/eligible/deleted/failed counts, deleted/failed rule details, and last cleanup error after add-on restart.
- Changing the configured cleanup schedule no longer clears the previous cleanup history shown in the HomeBrain UI.
- Uses an atomic temporary-file replace, matching HomeBrain's existing health-audit persistence pattern.
- Corrupt or unreadable persisted state is reported as a persistence error but does not stop the scheduler.
- Cleanup eligibility/deletion safety is unchanged.
