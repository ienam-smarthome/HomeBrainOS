# HomeBrainOS v0.16.150 — scheduler absence-label safety

v0.16.149 live verification confirms the probe-history cleanup guard works across recommendation sections, but synthesis still used unsupported labels elsewhere: `Not in inventory`, `Jobs scheduled for missing entities`, and `Orphaned Job Audit` / `remnants of deleted devices`.

This release adds a deterministic finalization guard that preserves the useful source discrepancy while rewriting those labels to source-scoped, unresolved language. Absence from `hubitat://context` or an unresolved bounded probe is not proof that a device is missing, deleted, orphaned, or that its scheduled job is stale.

Regression coverage reproduces the v0.16.149 live wording. No Hubitat state is changed.
