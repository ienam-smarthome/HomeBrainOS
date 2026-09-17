# Hubitat MCP AI 0.10.447

- Treat successful named-device history reads as evidence for a second model synthesis round instead of ending immediately with the generic deterministic event-dump template.
- Add deterministic temporal interval analysis for switch, contact, motion, lock, and valve history so duration arithmetic is grounded in authoritative timestamps rather than free-form model maths.
- Return pre-computed interval count, total active duration, longest active duration, continuity, and boundary-coverage metadata to the model.
- Mark incomplete boundary coverage as a lower bound instead of inventing a start or end time.
- Add a history-synthesis host hint that tells the model to answer the user's actual question from `temporalAnalysis` and to preserve the existing no-unproven-causation rule.
- Add regression coverage for the live Big Lamp pattern, equal timestamps, duplicate/non-state-change rows, incomplete boundaries, and DST offset changes.
