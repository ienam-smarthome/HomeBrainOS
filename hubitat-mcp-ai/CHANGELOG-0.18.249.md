# v0.18.249 — Reconcile native and journal activity before final claims

## General evidence integrity correction

The recent-edge Historical Journal recovery and its rendered explanation now cross-check successful native Hubitat event receipts **and** independently derived `homebrain_device_history` ON/OFF intervals. A missing low-level projection can no longer erase a source-attested native interval and lead to the inaccurate statement that native history returned no switch events.

- Native activity is identified by independently scoped device ID or verified label, bounded event time, successful nonmutating receipts and valid switch events or interval endpoints.
- The recent-edge recovery is bypassed when native switch evidence is already present in the requested window; the original MCP investigator remains responsible for explanation.
- When archived journal context is rendered, its text distinguishes native switch activity from separate journal observations and does not misstate archive data as the only source.
- No new MCP permissions, guessed controller identities, Hubitat writes, changes to all-app 48-hour Historical Journal retention, or claims that association is causation.
- Adds generic regression tests for actual native intervals, true empty histories, stale/unrelated/mutating evidence and exact switch reports.

## Remaining limitations

This corrects contradictory activity reporting, **not** full causal provenance. Follow-up architectural development must integrate source-attested dependency leads, iterative evidence-read planning, execution-log correlation and a causal completion gate. Full CI must be green before merging; live Home Assistant verification is separate.
