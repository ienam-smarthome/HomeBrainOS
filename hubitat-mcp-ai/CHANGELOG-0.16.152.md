# Hubitat MCP AI 0.16.152

## Scheduler ownership metadata discovery

The scheduler analysis has reached the limit of what can safely be inferred from encoded keys such as `app1418Once...` and `dev1089Recur...`. Those remain candidates, not authoritative owners.

This release adds a bounded, read-only schema discovery step to the existing `hub_get_jobs` payload:

- records top-level and nested **field names and row counts only**;
- explicitly reports whether the currently recognized `appId` or `deviceId` owner fields occur;
- highlights owner-like field names containing terms such as owner, app, device, parent, source, or installed;
- does not retain or render arbitrary values from those fields;
- does not promote an owner-like name to authoritative ownership without independent semantic verification.

The deterministic scheduler summary now exposes this schema information so the next live run can tell us whether the upstream Rule Server already returns a stronger ownership relationship that HomeBrain has not yet consumed.

This is discovery only. It does not modify Hubitat and does not change the existing rule that scheduler-key prefixes, inventory matches, missing IDs, and performance overlaps are not proof of job ownership or safe cleanup.
