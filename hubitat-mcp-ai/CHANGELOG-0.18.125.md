# HomeBrainOS 0.18.125 — Investigation V2 AI planner and evidence-led synthesis

## Implementation

- Adds `V2ModelProposer`, a structured JSON planning adapter over the
  **existing** `ChatTransport.chat(messages, [])` provider routing. The model
  sees a bounded case-file view and a *host-derived, read-only* tool schema.
  Its proposed reads are still checked by the existing V2 planner and host
  permissions; no model-emitted native tool calls are executed.
- Adds `evaluate_v2_with_model(... explicitly_authorised=True)` as an
  **opt-in-only** end-to-end evaluation path through the V2 read executor.
  The normal agent never invokes this path and no extra background MCP
  requests are created.
- Adds one no-tools synthesis model round to select relevant observations
  and rank *candidate* explanations.
- Adds `assemble_grounded_answer` to display actual, source-timestamped
  observations directly from the shared typed case file. All incident
  commands are retained regardless of whether the model selected them.
  Unverified hypotheses remain explicitly tentative. Missing history does
  not overwrite the command chronology.
- Adds test coverage for the real model transport with mocked HTTP, model
  tool-call refusal, evidence omissions, malformed JSON, unknown citations,
  provider failure fallback, identity/permission boundaries and full
  October incident retention.

## Intentional limitations

No live HomeBrain chat cutover, automatic shadow reads or Hubitat writes.
The AI ranks hypotheses and chooses evidence, but currently the host renders
verified observations; this is a safe initial synthesis contract, not
full freeform Claude-equivalent causal explanation. A future PR will add
atomic-claim verification and bounded model revision, then measured shadow
comparison against V1 and external reference answers.

## Rollback

The V2 evaluation functions remain unregistered in production routing.
The existing read/write agents and confirmation flow are unchanged.
