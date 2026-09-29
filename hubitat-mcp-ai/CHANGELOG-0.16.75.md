# Hubitat MCP AI 0.16.75

## Evidence-first performance synthesis

This release addresses the repeated performance-analysis grounding drift seen across the 0.16.70–0.16.74 live proofs without changing the established four-read / normally three-model-round production path.

### Root cause fixed

The API performance finalizer reused the current-turn metrics/performance/jobs/log payloads correctly, but the final synthesis context also contained the prose answer produced by the earlier tool-selection/reasoning phase. That prose could already contain unsupported claims such as blocking risk, CPU/load effects, reporting overhead, qualitative health thresholds, or speculative driver/network mechanisms. Telling the final model that the earlier draft was “not evidence” did not prevent it from being primed by that wording.

0.16.75 removes prose-only assistant conclusions from evidence-scoped performance final synthesis. Native assistant messages that contain actual `tool_calls` are retained so matching tool messages remain structurally valid.

### Evidence contract

A new `performance_evidence_first.py` module provides a dedicated final-synthesis contract:

- metrics support numeric values and explicit alert/state fields, not invented healthy/normal/stable thresholds;
- performance stats support execution time, call count, busy percentage, and ranking, not synchronous/blocking/time-out mechanisms or user-visible effects;
- scheduled jobs support returned schedule facts, not CPU/load causality or benefits from moving/staggering jobs;
- recent logs are observations and do not automatically explain longer-window performance totals;
- when configuration/implementation evidence was not read, recommendations must be inspection-first rather than exact edits;
- absence of an alert does not justify categorical “no optimisation needed” claims.

### Generic backstop

The evidence-first validator also fail-closes language exposed by the 0.16.74 live proof, including:

- conditional synchronous/blocking → stutter/delay speculation;
- reporting → background-overhead/log-growth/history-slowdown causality;
- qualitative “major outlier”, “exceptionally high”, “very healthy”, or similar unsupported thresholds;
- categorical memory/database optimisation conclusions based only on absent alerts;
- dramatic job-cluster wording where the evidence only establishes aligned timestamps.

### Regression coverage

The complete 0.16.74 live answer is included as a regression fixture. Tests also verify that:

- the final performance model does not receive the original prose draft;
- native tool-call assistant envelopes are preserved;
- the evidence-first contract is present in final synthesis;
- measured values survive deterministic repair;
- Markdown recommendation tables remain structurally intact;
- the existing four-tool / normally three-round performance architecture is not changed by this release.
