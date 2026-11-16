# HomeBrainOS V2 alpha.135 — passive round-phase cost measurement

**Status:** merged [PR #1707](https://github.com/ienam-smarthome/HomeBrainOS/pull/1707) at `63527853c42340b83ad0d701ccb62f55ba865491` after **4/4 exact-head CI workflows passed**. Installed alpha.135 acceptance remains outstanding.

## Source-real motivation (private 16 November alpha.134 capture)

An original, uncoached, read-only V2 alpha.134 first answer gave a
well-scoped recorded command issuer, subsequent device-reported outcome,
configuration evidence and explicit unknowns. Source-reviewed qualitative
score: **7/8 on one case**, not representative model accuracy or a
causally attributable version improvement.

The same source-reported technical performance showed:

- **8 provider model rounds**
- **366,837 provider-reported input tokens**, **11,923 output tokens**
- **~180.1 seconds provider-reported model processing**
- **~191.4 seconds browser elapsed**
- **5 successful original native reads**, **~7.5 seconds of tool attempts**
- first substantive draft was captured **after round 3**; source review
  and final audit continued through rounds 7 and 8, with 3 more original
  successful reads during review

**Caution:** Provider model time plus native-tool time is not an exact
wall-clock partition. A draft after round 3 was not yet a source-complete
or independently verified root-cause answer. The extra review found the
recorded command issuer and configuration while leaving the originating
event-time input unverified. No observed single-case speed or correctness
gain can be attributed to a particular model checkpoint.

## Bounded runtime implementation

Without changing any prompts or read/write dispatch, attach to each
already-recorded `model_round_metrics` entry (if provider timing metadata
is supplied):

- `phase`: one enumerated label — initial investigation, source review,
  causal follow-through, tool-free final claim audit, deadline finalization
  or prewrite model review
- `client_round_elapsed_ms`: local elapsed for the same existing model
  call, not additional model execution
- `source_receipts_before`: original received source receipt count
- `tools_offered`: number of tool definitions offered for this model round
- `model_messages_before`: count of conversation messages passed to model

The provider's original total/prompt/output counters remain intact. These
new fields include **no household source content, question, native tool
argument, device ID, answer text or native response**, and do not trigger
extra calls or scans. They are passive technical telemetry in the private
Technical JSON export only.

**Non-goals:** Removing final audits, forcing fixed model-read order, imposing
new hard latency/time limits, changing model/provider routing or reducing
the established safety checks. Any proposed optimization needs multiple
independent benchmark cases with source-reviewed quality, not one example.

## Private offline comparison

Run against one or more ORIGINAL browser Technical JSON exports (not the
pasted review prompt that wraps it), on a trusted machine:

```bash
python scripts/first_answer_latency_profile.py /private/answer-a.json \
  /private/answer-b.json --output /private/latency-comparison.json
```

- Exports only SHA-256 input reference, V2 version, model name, aggregate
  provider token/time counts, raw tool **counts**, phase-labelled round
  metadata and a note that quality is unmeasured. Original question,
  answer, logs, event timestamps, device identifiers and tool arguments
  are **not copied**.
- The output is PRIVATE, created once with owner-only permissions on POSIX;
  existing files are never overwritten.
- For alpha.134 and earlier, source stage trace may allow **derived** phase
  labels (`derived_from_stage_trace`). Such phases are NOT runtime-recorded
  truth. With no valid markers, phase is `unknown`.
- An aggregate should never compare models as faster at equal answer
  quality without matching questions, source scope, cloud cache/provider
  conditions and human review. Repeated prompt tokens may be served from
  cache; raw provider input counts are not a billing statement.
- Performance profiling is a separate tool from the human qualitative
  `first_answer_live_intake.py` and 53-case scorecard. Do not
  auto-populate factual/causal review grades from performance numbers.

## Tests and acceptance

Fictional Python tests cover new and legacy phase capture, actual
source-review and final-audit stage enumeration, no extra model/native
rounds, privacy of output, create-only permission, malformed phase fields,
tool-error counts and no fabricated quality score.

Exact-head GitHub V2 and full-suite CI must pass before merge. Installed
acceptance: update V2 Preview to alpha.135, capture one **fresh original**
Technical JSON read-only first answer, and confirm new phase fields appear
under `model_round_metrics` with the same number of original rounds and
source tool attempts. Report durations and real evidence quality separately.

**Next decision gate:** gather several independently scored read-only
causal/status/measurement questions across domains. Analyse per-round
phase costs on those samples. Only then trial a bounded review reduction or
selective context condensation if it can demonstrate a reproducible
latency/token improvement without losing verified command attribution,
outcome identity, original receipt coverage or safety.
