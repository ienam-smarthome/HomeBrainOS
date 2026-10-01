# 0.16.84 — Preserve diagnostic context across entity blocks

## Summary

0.16.84 keeps the accepted 0.16.81-0.16.83 performance retrieval, adaptive expansion, timing, and evidence-classification architecture unchanged. It fixes the final remaining context-propagation defect in the format-independent diagnostic guard.

The live 0.16.83 proof showed that the architecture was correct — five reads, zero exploratory agent model rounds, one synthesis round — and that the evidence-first validator was firing. However, two unsupported conclusions still survived because the post-synthesis state machine lost section/target context while traversing Gemma's Markdown.

## Root cause

Two presentation transitions were incorrectly treated as context boundaries:

- Numbered bold entity subheadings such as `**2. SenseCap D1 Settings Resource Usage**` were parsed as new top-level sections, which cleared the enclosing `Diagnostic Hypotheses & Recommendations` mode.
- Child fields such as `**Evidence:**` and `**Verification:**` cleared `current_target` when the child line did not repeat the entity name.

That allowed SenseCap's unsupported `every 5 to 10 minutes` cadence and LG's unscoped network/API verification step to survive even though the structural evidence classifier already had the correct boundaries.

## Fix

- Numbered bold entity subheadings now preserve the enclosing diagnostic/recommendation mode.
- Entity subheadings bind the current adaptive target when scoped, or explicitly clear it when the entity was not scoped.
- Child fields including Finding, Evidence, Conclusion, Diagnostic interpretation, Hypothesis, Verification, Action, and Next step inherit the current target unless they explicitly name another target.
- Mechanism-specific Verification/Recommendation lines are evidence-gated inside combined diagnostic/recommendation sections as well as dedicated recommendation sections.
- A generic `Cadence:` line is attributed to the source/signal when exactly one host-established regular cadence exists in the current evidence.

## Exact live regressions

The 0.16.83 live shape is covered directly:

- SenseCap's Evidence child inherits the SenseCap target and cannot retain an invented 5–10 minute cadence without host `regular_cadence` evidence.
- The repeated SenseCap activity remains reportable, but the answer keeps the explicit `activity != cause` boundary.
- LG webOS TV remains unresolved when not target-scoped, and its Verification child cannot prescribe network/API-specific investigation before targeted evidence is collected.
- Google Nest Hub's already-safe repeated-volume interpretation remains associated with Nest rather than borrowing SenseCap evidence.
- The anonymous regular cadence observation is attributed to `Halo3000x socket power ActivePower` when that is the sole host-established regular cadence.

## Architecture unchanged

- Quiet broad-performance case: 3 reads / 0 agent rounds / 1 synthesis.
- Strong-outlier adaptive case: max 5 reads / 0 agent rounds / 1 synthesis.
- No new Hubitat tool call.
- No new provider round.
- No broader diagnostic fan-out.
