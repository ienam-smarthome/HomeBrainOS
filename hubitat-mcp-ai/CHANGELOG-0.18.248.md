# v0.18.248 — Source-attested dependency leads (foundation)

- Adds `investigation_dependency_leads.py`, a bounded, read-only projection of independently verified app/device associations, app-issued commands and device-state observations.
- Original source timestamps and verified device identities are required. Failed, mutating, unsupported and collector-only records cannot establish new leads.
- Temporal proximity and association are never promoted to proven causal attribution; source coverage remains explicitly incomplete.
- Adds receipt-integrity and attribution-boundary unit tests; records the new runtime module in the canonical module map.
- The graph is **not yet wired into the original HomeBrain agent's model-directed investigation loop**, and does not alter any live investigations or Hubitat devices. Future work must integrate typed evidence and targeted read planning.
- Full CI validation and live deployment verification are prerequisites before merge/release.
