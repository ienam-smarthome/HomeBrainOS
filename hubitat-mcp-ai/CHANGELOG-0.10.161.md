# Hubitat MCP AI 0.10.161

## Changed

- Consolidated `HomeSnapshotService`, `TruthfulHomeSnapshotService` and
  `HybridTruthfulHomeSnapshotService` in the canonical `home_snapshot.py`.
- Preserved the base, truthful and hybrid installer APIs behind one shared,
  typed installation helper.
- Retained truthful forced-refresh behavior, missing-state safeguards,
  Cloud-first synthesis and local-provider disclosure.
- Removed the sibling-only `home_snapshot_truthful.py` and
  `home_snapshot_hybrid.py` modules after switching every importer.

## Validation

- Snapshot behavior and installer compatibility regression tests.
- Import and cluster analysis.
- Repository layout validation.
- Python compilation.
- Blocking release gate.
