# HomeBrain 0.17.14 — Evidence-to-claim verification

This release addresses three errors observed during the 0.17.13 physical light investigation: attributing an app-owned brightness command to a different notified listener, treating a zero-row execution log as proof of non-execution, and collapsing sensor events recorded on opposite sides of the OFF transition into one before-OFF statement.

## Changes

- Added a reusable source-bound verifier for uniquely scoped single-event causal answers. It compares actions with the exact command-event `producedBy` identity, rather than inferring ownership from the state event's `triggered[]` listeners.
- Kept optional names of notified apps in the physical state boundary graph, separately from actual command producers.
- A bounded empty log search establishes only that no execution entries were returned, not whether internal logic ran.
- Signed sensor timing is retained per source: a report after the OFF boundary cannot be described as before it. OFF command ownership remains unverified absent command provenance.
- Applied the same checks during final synthesis and final API serialization, with conservative behavior when the source event or command is ambiguous.
- Updated the shared synthesis instructions and regression tests for action ownership, empty log attribution, mixed before/after events, missing command provenance, and the app-initiated motion path.

## Boundaries

The verifier does not establish native bridge-to-controller mappings or who physically pressed a button. It does not modify devices, apps or permission controls. Performance and live accuracy must be rechecked after installation.
