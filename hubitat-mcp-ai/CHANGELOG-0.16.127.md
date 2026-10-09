# Hubitat MCP AI 0.16.127

## Fixed
- Reconcile Rule Machine entries that already appear in installed-app inventory using the same Hubitat ID.
- Report unique instance counts instead of adding the overlapping app and rule populations.
- Preserve source provenance and stronger broken or disabled markers when merging duplicate records.
- Add regression coverage for overlapping rule/app inventories and unresolved IDs.

## Safety
- Read-only diagnostic changes; no Hubitat configuration mutations.
- Runtime verification and dependency tracing remain outside this release.
