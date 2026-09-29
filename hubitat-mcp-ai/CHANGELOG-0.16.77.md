# Hubitat MCP AI 0.16.77

## Performance precision and observability

0.16.77 keeps the evidence-first performance architecture introduced in 0.16.75 and the canonical metric normalization from 0.16.76. This release focuses on making remaining corrections measurable and preventing unsupported precision from raw sources.

### Source-bound scheduler analysis

- Final performance synthesis now explicitly distinguishes whether a successful current-turn `hub_get_jobs` source exists.
- Without that source, the answer must not state job counts, alignment, cadence, `sessionTick`/`autoPoll` scheduling, or scheduler conclusions.
- With job evidence, only the returned job facts may be reported; existing CPU/load and configuration boundaries remain unchanged.

### Conservative raw-log counting

- Raw recent-log rows remain observations.
- The model must not manually derive an exact event/update count from raw rows unless a current-turn tool or host-produced summary explicitly supplies that filtered count.
- Otherwise the answer uses conservative wording such as “multiple updates” while preserving an observed time span or cadence.
- The deterministic evidence-first backstop covers exact-count variants exposed by the 0.16.76 live test.

### Model-round observability

- Performance metric rows now separate total model participation into pre-finalizer **Agent model rounds** and the single **Performance synthesis model round** when the finalizer timing proves the standard one-pass path.
- This makes a 4-round live result diagnosable as, for example, 3 evidence-gathering rounds + 1 final synthesis round rather than suggesting that the finalizer silently used multiple provider repairs.

### Repair-reason observability

- Performance validation records request-local, fixed-vocabulary issue categories only.
- When deterministic performance repair occurs, metric rows can identify the reason as:
  - Log/performance causality
  - Live performance semantics
  - Evidence-first performance contract
- The trace is consumed once per response and contains no prompts, device names, credentials, session IDs, or tool arguments.

### Regression coverage

- Exact 0.16.76-style raw-log manual-count wording.
- Scheduler-source absence/presence contract.
- 4 total model rounds split into 3 agent rounds + 1 performance synthesis round.
- Request-local repair reason is surfaced once and then cleared.

The existing performance finalizer remains single-provider-pass, normalized payload reuse remains unchanged, and no additional Hubitat reads are introduced by this release.