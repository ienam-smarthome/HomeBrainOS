# Hubitat MCP AI 0.16.78

## Host-planned performance evidence path

0.16.78 keeps the evidence-first final synthesis introduced in 0.16.75 and the canonical normalization/precision work from 0.16.76-0.16.77, but removes the unnecessary model-directed evidence-planning phase for broad performance requests that also ask for recommendations.

For that request class, the host now acquires the bounded evidence set directly through the existing `ToolExecutor`:

1. `hub_get_metrics`
2. `hub_get_performance_stats`
3. `hub_get_logs` (`since=30m`, `limit=100`)

`hub_get_jobs` is added only when the user's objective explicitly mentions scheduler/job/polling cadence. The model still authors the final analysis; the host only owns evidence selection. This avoids unrelated `homebrain_hub_info_snapshot(scope=full)` reads, tool discovery, gateway rejection, and pre-synthesis model rounds for the normal broad-performance prompt.

## Repair-reason propagation

Performance validator reasons are now copied into the serializable response metrics before the request-coordinator child task returns. This fixes the ContextVar task-boundary gap exposed by the 0.16.77 live proof, where `performance_api_deterministic_repair=1` was visible but no `Performance repair reason` metric row appeared.

Fixed-vocabulary reasons remain privacy-safe and now include:

- Log/performance causality
- Live performance semantics
- Evidence-first performance contract
- Literal log observation preservation

## Literal WARN/ERROR preservation

A new evidence-aware log-observation guard restores a cited WARN/ERROR from the authoritative current-turn `hub_get_logs` receipt when causal/generic repair prose would otherwise overwrite the literal observation. The log fact and the causal boundary are rendered as separate sentences. Clean literal warning lines are left unchanged.

This specifically prevents malformed hybrids such as the 0.16.77 MCP Rule Server warning where a real `slow internal GET` observation was replaced mid-line by generic overhead/history wording.

## Observability

- `broad_performance_host_plan` identifies the deterministic evidence path.
- `broad_performance_host_plan_jobs` shows when scheduler evidence was explicitly requested.
- Repair categories are persisted as response counters so the parent API serializer can always display them.
- The existing Agent model rounds / Performance synthesis model rounds split remains unchanged.

## Expected live shape

For `Analyse my Hubitat performance and recommend improvements.` the normal path is now:

- 3 Hubitat reads: metrics, performance stats, recent logs
- 0 pre-finalizer model rounds
- 1 evidence-first performance synthesis model round
- no tool discovery
- no gateway rejection from exploratory planning
- no full hub-health snapshot

Scheduler/job evidence remains opt-in when the request actually asks about it.

## Regression coverage

0.16.78 adds tests for:

- broad-performance request classification,
- the exact three-source default host plan,
- scheduler-source opt-in,
- accepted host-plan request metrics,
- serialized repair-reason presentation across the async task boundary,
- reconstruction of the malformed 0.16.77 MCP Rule Server WARN line from current-turn evidence,
- and non-interference with already-clean literal warning observations.