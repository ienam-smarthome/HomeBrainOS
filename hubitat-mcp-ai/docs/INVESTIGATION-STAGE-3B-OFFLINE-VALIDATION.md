# Stage 3B — offline cross-domain investigation planning validation

Base: main v0.18.275. Source metadata: **v0.18.276**, shadow-only.

## Aim

Measure whether the existing Stage 3A read frontier can select the next
discriminating source READ while preserving source scope, history limitations
and the original model's autonomy. This is **offline regression validation**,
not production deployment, shadow traffic recording, or a new planner.

`stage3_planning_evaluation.py` runs the existing Stage 3A frontier and the
existing V3 `causal_source_feasibility.py` on identical retained fixtures.
Expected read sets are independently authored by tests and passed ONLY to
the scorer, never to the frontier; no oracle information can influence
actual candidate choice.

## Measured dimensions

- **Precision@k:** fraction of offered top-k choices matching the fixture's
  independently declared useful next reads.
- **Oracle recall@k:** fraction of expected next reads recovered within k
  offered choices. A fixture without expected reads reports null recall,
  not an artificial success.
- **First useful rank** and suppressions: exact previous attempts (including
  failed/empty), unverified IDs, invalid/unbounded scopes and leaves absent
  from the validated current read-tool catalog.
- **Invalid/unauthorised offers:** any selected proposal failing the same
  schema/catalog checks used in the reference evaluator.
- **Legacy comparison** only when the existing source-feasibility function
  returns a meaningful grouped witness-ledger packet. For other domains the
  old implementation is **not comparable**, never represented as 0% quality.
- A case-level **no causal/absence proof** invariant. Neither a scored match
  nor a successful source query is evidence of historical source completeness.

## Independent domains / boundary cases

1. Paired lighting with five source-timed cycles, reception-only input and
   unexplained initiating command; a source-scoped input dependency lead.
2. Heating with a verified thermostat setpoint command producer and a
   separately unverified listener.
3. Ventilation with a humidity-controller command and a narrow source
   humidity-history lead.
4. Offline power device with queried-but-empty native history and a bounded
   power-history discriminator.
5. Failed historical read with a *different*, bounded follow-up, while
   blocking repetition of the same failed exact read.
6. Security with forged app IDs, unsupported modifying leaves and
   secret-bearing/unbounded arguments.

Additional tests cover malformed dependency metadata, 40-case suite caps,
oracle isolation, result privacy, deterministic scores, and source-clock
versus collector-clock uncertainty.

The fixture suite verifies that the eight expected leads are retrievable
within top three, but this is **not** a measured improvement over current
live HomeBrain, nor a representative production data set. In the current
suite only the paired-light incident is eligible for direct V3 source-frontier
comparison. More historical traces from other domains are required before
any broad model-quality claim.

## Safety / rollout gates

- No active agent, tool executor, HTTP handler or answer publisher imports
  the new evaluator. Zero MCP calls, device writes, network requests, DB
  migrations, HA changes or production feature flags.
- A malformed `appsUsing` dependency response is now ignored, not treated
  as verified app IDs and not allowed to crash Stage 3A.
- Do not enable new planning or publishing based solely on fixture metrics.
- Stage 3C must separately review the real MCP catalog schema, introduce
  explicit opt-in and rollback, instrument passive non-actioning comparison,
  verify cross-domain live parity, and complete more genuine historical
  evidence regressions before any active tool-choice behaviour changes.
- CI must pass both original regression suite and new Stage 3B tests.

Rollback: revert this additive PR. Existing v0.18.275 behaviour is unchanged.
