# Hubitat MCP AI 0.16.114

## Changed

- Reuses the existing read-only System Check for broad chat requests about hub logs, device and app statistics, issues and fixes, rather than returning only a recent performance sample.
- Includes device health, low batteries, reported unreachable devices, automation attention and grouped warning/error logs.
- Separately lists inactive/quiet devices without diagnosing them as offline without direct reachability or explicit reporting-contract evidence.
- Adds top device/app performance rows and at most one targeted six-hour log read per strong device/app outlier. Performance load does not prove a driver fault or root cause.
- Preserves incomplete-source and log-retention caveats, and explicitly makes no automatic changes to apps, rules or devices.
- Prevents the automation-status shortcut from intercepting broad system-audit requests.

## Validation

- Adds focused regression tests covering routing, neutral stale states, missing performance data, scoped logs, and read-only behaviour.
- Full CI test result is tracked in the pull request.
