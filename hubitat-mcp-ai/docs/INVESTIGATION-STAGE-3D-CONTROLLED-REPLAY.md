# Stage 3D — controlled offline replay of model-selected evidence reads

## Source-only milestone (v0.18.278)

This milestone adds a **replay evaluator**, not a live model planner or a
deployed Home Assistant feature. It extends the previously merged Stage 3A
candidate frontier, Stage 3B independently scored fixtures and Stage 3C
default-OFF passive model-loop observer. Production read execution and answer
publication remain completely unchanged.

### Input and provenance contract

`evaluate_stage3d_replay(cases, top_k=3)` consumes bounded,
**already supplied** in-memory round snapshots:

- `receipts_before`: retained read receipts as they existed **before** the
  model chose a read. Later replies may only be added to later rounds.
- `model_tool_calls`: the original model tool-call-shaped responses,
  including their exact gateway and request arguments. **This code does
  not invoke a model.** Constructed test calls do not count as captured
  production outputs.
- `declared_tool_schemas`: the exact declared read gateway operation enums
  presented to the model in that round. Free-text descriptions, previously
  successful gateways and guessed names confer no authority.
- `facts`: optional existing V3 grouped witness projection.
- `expected_reads` (optional): separately authored independently
  source-attested, declared, bounded useful read fingerprints, used **only
  after** computing both model and Stage 3A frontier choices.

Each case must truthfully label `trace_origin` as
`constructed-fixture`, `anonymised-reconstruction`, or
`user-labelled-redacted-trace`. These are **claims about the input**, not
independent proof of provenance. The included six-domain regression uses
constructed model-call sequences, even where the associated lighting evidence
comes from the anonymised five-cycle historical reconstruction. There is
currently **no verified, captured production model/tool-choice trace** in this
suite. That is a deliberate coverage limitation.

No secrets or private names should be supplied to the replay evaluator.
It emits only numeric aggregates, safe fixture labels and fixed status
strings; individual device IDs, tokens, commands, actual tool arguments,
private source text and model messages never appear in the result.

### Comparisons and what they establish

For each pre-round state, the harness compares:

1. The provided original model's positively catalog-mapped READ proposals
   **in their original proposed order**.
2. The existing Stage 3A frontier over **the same proposals, the same prior
   receipts, the same declared operation set** and optional existing V3
   evidence-ranked candidates.

It reports expected-read precision/recall at top-k, duplicate prior exact
attempts, IDs lacking independent source evidence, malformed scopes and
unsupported gateway/operation calls. Scores are reported only where an
independent expectation was supplied. Missing expectations result in null
utility metrics, never invented successes, failures or causal conclusions.

A higher replay score on constructed proposals establishes that the
deterministic validator filtered those examples. It does **not** establish
that a new model plans better, that present-day Hubitat will provide the
required information, or that the model's natural-language answers or
end-to-end latency improved. Model-chosen READs remain the only live choice.
No threshold in this module auto-enables the new planner.

### Bounded privacy, resource and safety gates

- Up to 24 cases, 12 rounds/case, 160 previous receipts/round, 16 model
  calls/round and 60 declared schemas examined by the existing observer.
- Any receipt scope beyond the trusted bound fails closed. Capped cases,
  rounds, calls and choices report omissions rather than claiming completeness.
- Replayed read calls **never execute**. No MCP, network, Home Assistant,
  Hubitat, database, filesystem or model client actions occur in the module.
- A checked-but-empty source or an attempted failed read is not proof of
  historical command absence. Source event clock, collector reception, app
  command issuer, listener and physical acknowledgement remain distinct.
- No additional agent import, runtime flag, new permission or publication
  output. Stage 3C passive observation stays default OFF.

### Regression set

Six domains: paired lighting, verified thermostat controller, humidity-driven
fan, offline power telemetry, unsuccessful native history and unsupported/
secret-bearing proposals. Tests additionally cover multi-round pre/post
receipt snapshots, changed bounded history windows, independent-oracle
isolation, missing oracle, malformed/unsupported tool catalog, duplicate
attempts, output privacy, provenance labels and deterministic replay.

### Acceptance criteria and next step

1. Entire Python, release metadata, smoke and HomeBrain validation suites
   must pass at the exact PR head.
2. Inspect changed files and review before merge; no merge on failed checks.
3. Preserve `stage3_shadow_mode="off"` for the installed add-on. No live
   measurements or production deployments are part of this change.
4. **Before a live shadow trial or Stage 4 model-authored publisher rollout**,
   obtain explicit deployment approval, privacy-review of sanitized trace
   collection and an emergency rollback path. Evaluate real recorded model
   traces across several domains, verify tool schema adapters and compare
   not only next-read efficiency but evidence and final answer fidelity.

Rollback: revert the additive Stage 3D PR. No live configuration or device
changes require undoing.
