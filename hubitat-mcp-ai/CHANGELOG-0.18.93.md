# HomeBrainOS 0.18.93 — AI-directed routing for read-only investigations

## Background

The 24 October Claude comparison exposed a classification failure: the user asked for a thorough investigation of one device, including app logs, schedules and drivers, but HomeBrain used a broad System Check route because keywords such as `comprehensive`, `apps`, `logs`, and `scheduled jobs` appeared together. That route delivered a fast snapshot and optional no-tools AI summary instead of permitting model-directed tool selection.

The 0.18.92 patch preserved requests with an explicit numeric device ID. This release addresses the **remaining ambiguity** for named-only incidents and overlapping terminology without adding more special-case keyword branches to decide the route.

## Design

- **Model chooses the read workflow:** When multiple existing read-only fast paths are eligible (comprehensive audit, automation diagnostic, or performance report), run one bounded no-tools model round with the original user's question. It returns only a structured route label: `model_led`, `system_audit` or `performance_report`.
- **One model-led MCP investigation by default:** The host interprets invalid, late, failed or unsupported model replies as `model_led`—a normal iterative MCP investigation. The user no longer has to remove words like `comprehensive` or `logs`.
- **Host enforces scope:** A whole-hub report requires clear user-specified whole-system scope. Aggregate performance mode requires an actual performance question, not a named device or an active causal incident. The AI cannot authorize Hubitat writes, run an MCP tool in its routing call or change the user's selected model tier.
- **Explicit shortcuts stay fast:** Deliberate whole-hub reports (e.g. 'comprehensive hub audit', 'audit my entire Hubitat system', or 'review all devices') and aggregate scheduled-job efficiency reports retain their explicit deterministic workflows without a routing model round. The short command `Run system check` stays immediate. Exact numeric single-device and Groovy source investigations already use their safe priority path.
- **Model decision persists across request-local shortcuts:** A request-local ContextVar signals that `model_led` was chosen, so the status presenters cannot replace the real investigation with a quick summary. The route is reset in `finally`.
- **No extra performance rewriter:** When the model chooses `model_led`, the API retains its investigative answer rather than sending it to a broad performance synthesis pass.
- **Observability:** Counter metadata records route arbitration and whether it selected model-led, a full report, performance mode or fell back from invalid/unsafe decisions.
- **Safety:** Explicit state-changing requests do not enter read-only arbitration; the existing action approval, identity, permission and write reconciliation layers remain authoritative. The performance-host shortcut now also explicitly rejects mutation requests.

## Limits and expected effect

AI routing introduces a small additional model round for ambiguous read requests; it may improve investigation quality at a modest latency cost. A route vote does not prove that Gemma will choose the best MCP tools or reach Claude-quality root causes. The existing Model MCP tool loop, evidence-policy limitations, tool availability and timeout budgets still determine investigative depth. Testing needs to measure source coverage, chronology, actual causal reasoning and model rounds, not response speed alone.

No live Hubitat devices, rules, apps or saved add-on options were changed. Free-tier requests stay on the existing free-provider path. No paid escalation is initiated by the routing module.
