# HomeBrain 0.17.39 — Investigation routing metrics hotfix

## Live regression

Version 0.17.38 correctly routed the requested historical motion-lockout
investigation past the configuration-only Rule Machine shortcut, but then
raised `Unsupported metric counter: investigation_snapshot_shortcut_bypassed`.
The new instance call `self.request_metrics.increment(...)` was missing
from the strict privacy-safe `RequestMetrics.ALLOWED_COUNTERS` registry.

## Changes

- Register `investigation_snapshot_shortcut_bypassed` in the request metric
  allowlist. Preserve strict rejection of arbitrary/private metric keys.
- Extend the existing repository-wide AST metric contract regression to
  check both free functions (`increment_active_metric`, etc.) and the
  instance methods (`self.request_metrics.increment`,
  `observe_counter_max`, `observe_ms`, `add_ms`).
- Add a direct active-request test proving the new routing counter can
  increment without raising while unknown keys still fail.

## Safety

No Hubitat writes, device changes, automation edits, historical journal
migration, new polling, or configuration changes. This is solely metric
registration and preventive static test coverage.

## Live validation

After updating to 0.17.39, repeat the **exact same** read-only app 4019
manual OFF/motion-lockout question. It should proceed past the snapshot
shortcut without HTTP 502 and obtain a historical investigation receipt,
or give explicit historical source failures instead of current config only.
Original action/lockout causality still requires execution evidence.
