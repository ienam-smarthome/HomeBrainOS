# HomeBrainOS 0.18.189 — Evidence-derived coverage and safe hub metrics

## Live regression

A 28 October 2026 v0.18.188 native V2 investigation of Google Nest Hub
(device 7934) took 13.921 seconds with seven successful reads. It
retrieved the three historic warning groups (43 sampled runQ rows, 27
excessive-load rows, one setVolume row), an online/idle device state and
hub metrics, but never read device command/event provenance. Two tool
discovery reads consumed precious model rounds. Although hub_get_metrics
returned current and trend data, the native safe projection discarded the
numeric health readings. The final source fallback therefore did not
identify command issuers or independently assess hub-performance impact.

## General improvements

- Preserve a bounded numeric/boolean projection of hub_get_metrics
  current readings and trends, retaining measurement timestamps and
  trend-coverage counts. Exclude credentials, endpoints, user identifiers,
  IP addresses and source file paths. Empty/uninterpretable metrics are
  explicitly flagged rather than treated as normal.
- Introduce a source-receipt-based coverage evaluator: a verified device
  with target-specific WARN/ERROR evidence but no scoped event history has
  an identifiable actor-provenance gap. The evaluator does not classify the
  user's question by keywords or invent source facts.
- If the model has exhausted the nominal investigation rounds but still has
  available read/time budget, it receives ONE bounded opportunity to
  choose a discriminating READ. The suggested device-event operation
  must already be present on the authenticated live read manifest or
  independently verified discovery map. The model can instead decide the
  missing evidence does not matter. No automatic extra hub read occurs.
- Track semantic duplicate tool-discovery results: the model receives a
  prompt to use independently offered source reads instead of repeating
  the same discovery.
- Record outstanding actor-provenance gaps, the bounded challenge and
  duplicate discovery in native diagnostics for live benchmark review.
- Keep full read receipts, type-separated app/device IDs, host read-only
  safeguards, partial historical coverage and skeptical physical-causality
  interpretation. Production Main Ask is unchanged.

## Acceptance and limits

Tests replay the six-round live pattern in which the model spends two rounds
on equivalent discovery results, then chooses a seventh model-directed
device-event read after a coverage challenge. Separate cases verify safe
numeric metric projection, retention of zero/false readings, repeated
tool-discovery fingerprints, absence of mandatory event reads for whole-hub
questions, and no false assertion that an issuing app caused a driver stall.

This still does **not** establish the internal cause of runQ/setVolume
delays or independently confirm hub-wide load causation. A model can reject
the proposed follow-up read, and the new source coverage challenge does
not constitute full claim-to-evidence validation. Source-derived numeric
metrics remain reported hub measurements rather than independently
calibrated physical observations.
