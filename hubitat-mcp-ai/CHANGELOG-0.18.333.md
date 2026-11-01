# v0.18.333 — Q1 single-source clock consistency in telemetry answers

## Scope

The recent v0.18.332 read-only device-health investigation rendered the **same stored timestamp disagreement twice**: the typed device-history answer independently recalculated it, then the shared completion boundary appended its own structured clock assessment. This duplication pushed a useful uncertainty into a repetitive technical report.

The new release passes the **existing structured source-clock assessment** into the generic typed-history renderer and renders one qualified warning alongside the saved device state. If no typed event history is available, the shared completion layer still reports the conflict. Standalone renderers without the shared assessment retain the original source-derived fallback.

- Keep the status/broker vs endpoint distinction as a **possible** interpretation, not an attested driver method.
- Preserve `investigation_coverage.telemetryClockConsistency`, source histories, unresolved `rootCauseVerified` and `questionResolved`, command/physical non-proof and read-only policy.
- No new model/provider round, tool call, device write, network action or additional evidence query.
- Unit and cross-domain tests check a single rendered warning, matching/missing assessments, direct-renderer fallback and technical provenance.

## Quality measurement and limits

The two available live results were not run against an identical immutable source packet. The observed v0.18.331 run used **43.533s**, **10 model rounds**, **13 tool calls**; v0.18.332 used **55.132s**, **11 model rounds**, **13 tool calls** with different evidence and source-selection paths. The latter contained an unrelated whole-hub read and unsuccessful method-source investigation. These are diagnostics, **not proof that v0.18.332 caused a 27% slowdown** or that v0.18.333 improves latency/Claude parity. The official fixed-case quality score remains **NOT MEASURED**.

This is a small general evidence-presentation correction, not restoration of unconditional model prose publication. Do not shorten required source checks for speed without controlled cross-domain evaluation.

## Rollback

Revert to v0.18.332 if the single-clock warning loses important information in other devices. No stored configuration or migration is involved.
