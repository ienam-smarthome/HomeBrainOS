# 0.17.95 — Actual provider model reporting and conservative paid routing

- Captures model and cloud/local provider only after a successful HTTP model round, using request-local metrics rather than mutable shared state.
- API `model` now identifies the last successful provider round. Per-round successful model metadata is provided as `metrics.model_round_details`; no credentials or evidence content are included.
- Hybrid paid-model routing no longer charges for a mere mention of `rule`, `sensor` or `automation`; analytical wording is required.
- A bounded API-side history coverage check prevents a conclusion that *all* checked evidence is from a single date when the same turn includes verified command receipts on another date; this is not proof that a separate focal event occurred.\n- Regression tests verify request-scoped data, date-scope claims and free/paid selection.

Limitations: This release does not implement evidence-driven paid escalation or fully repair historical event correlation; those require separate live-scoped tests. Spend ledger remains an estimated reserve, not provider billing. No Hubitat writes.
