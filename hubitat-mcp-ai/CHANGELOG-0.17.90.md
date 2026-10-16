# 0.17.90 — Receipt-aware conclusion calibration across HomeBrain routes

## Motivation
Three independent v0.17.88 live reports returned meaningful evidence but mixed supported observations with unsupported strength:
- Fridge contact: 7 observed 51-second intervals and explicit 4-minute wait/cancel logs, but duplicated the summary and called the automation *perfectly aligned / exactly as configured* despite incomplete event-source integrity.
- Broad system audit: a fresh Hubitat `lastActivity` timestamp was described as a status-vs-activity conflict while the source of the event was not established; driver-generated health changes can refresh activity without physical telemetry.
- Bedroom 3 Mesh: repeated no-data watchdog warnings are valid evidence of a sustained watchdog data gap, not definitive proof of a *dead connection* or a *complete telemetry failure*. Intermittent recovery outside the returned log window is not excluded.

## General architecture
- New `evidence_claim_calibrator.py` is invoked after shared completion for **all** `/api/ask` and `/api/chat` routes, using the same current-turn receipts. It preserves original evidence and response metadata while calibrating a narrow set of unqualified high-certainty, physical-initiation and completeness claims only when relevant partial/incomplete history or targeted watchdog logs are present.
- Repeated long standalone summary lines are collapsed once. Tables, lists and source event rows are not touched.
- The health audit's recent-activity message now explicitly distinguishes source-unverified device activity from a fresh physical packet. It does not treat a recent driver/watchdog health event as proof of recovery or offline-state contradiction.
- A privacy-safe `evidence_claim_calibrations` counter documents when the final text was changed.

## Boundaries
This gate is deliberately **not** a generalized natural-language truth oracle, proof of any new cause or a replacement for source integrity. It does not change event times, compute new history totals, edit automation settings, command devices, add MCP privileges, or modify the historical journal. Confidence remains appropriately strong for fully verified records. Source-side topology and origin investigation are still required for true causality.

## Validation
Regression cases: duplicate fridge interval text, incomplete-source confidence, truly verified history unchanged, scoped watchdog no-data versus missing/unscoped logs, API outcome retention and audit activity qualification. Full Python/add-on/container/repository checks required before merge.
