# HomeBrainOS v0.16.140 — Scheduler inventory metric registry hotfix

## Fix
- Register `scheduler_inventory_crosscheck`, `scheduler_inventory_timeout`, and `scheduler_inventory_read_failure` in the strict request metrics counter allowlist.
- Prevent the v0.16.139 `Unsupported metric counter: scheduler_inventory_crosscheck` failure when a scheduled-job review reaches bounded app/device inventory reconciliation.
- Add regression tests using the **production** `RequestMetrics` collector for the scheduler cross-check and inventory timeout paths. Previous tests used an unrestricted metrics mock and could not detect this failure.

## Scope and safety
- The v0.16.139 scheduler evidence/inventory logic and six-second read limits are unchanged.
- No Hubitat app, device, rule, driver or schedule changes.
- Live Hubitat inventory cross-check verification remains pending after updating the add-on.
