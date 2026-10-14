# Hubitat MCP AI 0.17.54 — semantic investigative evidence completion

## Changes

- Introduce `general_evidence_completion.py` with a typed ten-class source
  inventory. Each category requires a successful, read-only, correctly
  scoped execution receipt, not a discovered tool or model claim.
- The opt-in semantic planner may now request precise required evidence
  classes, alongside human-readable investigation goals.
- When an investigation reaches a no-tool final answer with required source
  classes still missing, HomeBrain performs one bounded model-directed
  follow-up using the actual missing classes.
- If evidence remains incomplete after that follow-up, final prose states
  which classes were unchecked. Metrics record the retry and gap.
- Distinguish "a source was checked" from "a historical cause or current
  communication capability was proven".
- Exclude basic inventory/navigation reads and malformed double-wrapped
  gateway arguments from satisfying targeted device-source requirements.
- Add read-only unit tests for source classifications, incomplete coverage,
  zero-row log reads, and model planning contracts.

## Scope

This is a deliberately limited foundation for evidence completeness.
The semantic task engine remains opt-in (default `false`). It applies
directly to model-led investigative turns that reach the general MCP loop;
specialised host shortcuts retain their existing investigation coverage
assessment and may bypass this new follow-up. A checked source class
does not prove a fact, event origin, complete time window, or rule execution.

No Hubitat write capabilities are added. Existing read/write permissions,
confirmation gates and source-specific claim validations remain in force.
