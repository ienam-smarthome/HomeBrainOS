# 0.18.14 — Cross-domain hypothesis checkpoint

## Changed
- Extend the existing optional semantic planner to propose two or three contrasting candidate explanations for an investigation, each with a distinguishing question and declared read-source class.
- Reject invalid, duplicate, unsupported or single candidates. Never include investigative candidates for routine reads, proposals or writes.
- Pass those candidates to the existing request-scoped investigation checkpoint. Indicate whether the required class of evidence was successfully checked, while leaving every hypothesis verdict unverified.
- Surface unchecked discriminating questions for one bounded existing read-only follow-up, without opening additional permissions or repeating known source calls.
- Preserve current provider budgets, strict MCP safety contracts and existing direct source code investigation.

## Validation
Added tests for cross-domain candidate parsing, untrusted source-kind rejection, duplicate handling, failed reads, checked-but-empty history, and strict separation between a source read and proof of a cause.

## Limitations
This is phase one of general-purpose hypothesis comparison, not an automatic causal verdict engine. Live integration testing remains necessary after CI. No smart-home configuration or stored settings were changed.
