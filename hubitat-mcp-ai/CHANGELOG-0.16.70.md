# Hubitat MCP AI 0.16.70

## Performance synthesis latency and grounding

This release refines the 0.16.69 broad-performance path after live proof showed that evidence reuse and the four-call tool contract were correct, but the API finalizer could still spend roughly 25 seconds in a second cloud-model repair cycle and allow several unsupported causal/prescriptive phrases through.

### Changed

- Broad performance API finalization now uses **one provider synthesis call**.
- If deterministic validation detects a conflict, the coordinator reuses the same first synthesis draft and returns its deterministic localized correction instead of making a second provider request.
- `model_rounds` therefore normally increases by one during API performance finalization rather than by two.
- Added `performance_api_model` timing for the final synthesis provider call.
- Timing presentation now distinguishes **Provider (agent phase)**, **Agent phase**, **Performance synthesis**, and **Performance finalization** instead of labelling the pre-finalizer phase as an ambiguous total.
- Added `performance_api_deterministic_repair` observability when a model repair round is replaced by deterministic correction.

### Semantic grounding

The live performance guard now fail-closes the exact 0.16.69 overreach patterns:

- overall outliers described as already "impacting efficiency";
- high execution time described as able to "block hub threads" without implementation evidence;
- aligned scheduled jobs described as causing momentary CPU spikes;
- direct advice to stagger job start times without reading the responsible app/rule configuration;
- qualitative "highly efficient" device labels without an evidence-backed threshold;
- "Stability & Connectivity Issues" headings inferred from recent error logs alone.

Measured values, recent log observations, hypotheses, and configuration-backed recommendations remain separate.

### Regression target

For `Analyse my Hubitat performance and recommend improvements.` the normal target is:

- four useful tool calls: metrics, performance stats, jobs, and one bounded recent-log read;
- no duplicate performance snapshot reads;
- database size preserved in MB;
- three model rounds total when the original agent used two rounds;
- one performance synthesis provider call;
- deterministic localized correction instead of a second cloud-model repair;
- no unsupported blocking, CPU-spike, staggering, efficiency, or stability claims.
