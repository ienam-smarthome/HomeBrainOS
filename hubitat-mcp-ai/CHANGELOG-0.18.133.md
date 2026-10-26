# HomeBrainOS 0.18.133 — clock-grounded hypotheses and read-plan diagnostics

- Rejects model-authored hypotheses that assert ambiguous bare clock times or clocks not matching their cited source records in the named timezone. This prevents a 00:41 BST event being described as 23:41 without explicitly saying UTC. Rejection never affects canonical history evidence.
- Enhances planner MCP schema projection with nested required fields and additionalProperties=false so it can propose correctly shaped read-only calls without weakening the host schema and permission gates.
- Surfaces bounded host read rejection reasons, planning round/read counts and current app identity metadata in the expandable V2 technical report, making `no_approved_discriminating_reads` debuggable.
- Reports that a rejected plan is not evidence that source data is absent. Existing user-friendly evidence timeline remains separate from the technical details.
- Safe admission/read-only execution and production V1 are unchanged. Live model comparison remains required.
