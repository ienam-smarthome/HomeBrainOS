# Hubitat MCP AI 0.16.76

## Performance evidence normalization

- Canonicalizes explicitly unit-labelled free-memory metrics before they reach final performance synthesis. Explicit `KB`, `MB`, `GB`, or byte values are exposed as `freeMemoryMB` while the original upstream value is retained for provenance.
- Deliberately does **not** infer a unit from an unlabeled numeric `freeMemory` value.
- Keeps the existing database compatibility normalization and the 0.16.75 evidence-first synthesis architecture unchanged.

## Evidence-first wording contract

- Final synthesis must prefer canonical normalized metric fields over raw/provenance aliases.
- Returned performance ordering is described literally (for example highest returned `pctTotal`) instead of being promoted into “primary consumer” or “highest impact” judgments.
- Numeric `stateSize` remains a measured value unless the current source provides a threshold/classification.
- Job clusters are reported as shared timestamps rather than qualitative high/severe/massive concentration labels unless evidence defines such a threshold.
- Recent log cadence is reported numerically where possible rather than inventing a “high-frequency” threshold.
- Without configuration evidence, call/report/job volume recommendations remain inspection-first and do not prescribe reduction.

## Regression coverage

- Adds explicit free-memory unit normalization tests, including a fail-closed unlabeled-number case.
- Adds the complete semantic variants exposed by the 0.16.75 live performance result as regression coverage.
- Preserves the established broad-performance architecture: normally four Hubitat reads and three total model rounds.