# Stage 4H — Complete-answer reference accuracy (offline, synthetic)

**Proposed version:** 0.18.288; source-only successor to merged 0.18.287.

## Why this stage

Stage 4G demonstrated real Qwen2.5 3B authored four synthetic investigation
answers (seven sentences and 5/5 expected source citations). Two
model reviewers agreed in only three of seven sentence reviews; four
reviews disagreed. **No independently adjudicated reference judgment
exists for the exact sentences Qwen generated**, so those outputs
cannot honestly be assigned a factual-accuracy score.

Stage 4H evaluates the sentence-review pipeline against **eight
complete, pre-authored synthetic answers with separately written
reference labels**. This measures whether the two actually running
reviewer models can distinguish complete safe explanations from
plausible but unsupported causal claims, and from explanations that
are true yet leave out material source evidence.

## Eight complete-answer references

| Domain | Reference answer classes |
| --- | --- |
| Lighting | Adequate source explanation; invented motion initiator |
| Heating | Adequate setpoint explanation; invented boiler ignition / valve movement |
| Ventilation | Adequate OFF-command explanation; invented humidity cause |
| Contact/history | Adequate collector timestamp **and** coverage gap; true but incomplete answer omitting the history gap |

Every answer has two full natural-language sentences, source fact IDs,
an independently specified expected fact set and an answer-level
reference label: `adequate`, `unsupported` or `incomplete`.
These labels are curated against constructed examples and **are not
authenticated as real-world truth**.

A source-matched citation can accompany an invented cause; the
Stage 4A host source-validator checks the citation but cannot
semantically verify the sentence. The expected source-fact set is
checked separately from sentence entailment. A true answer that
does not cite every required source fact fails completeness even if
both reviewers accept its words.

## What runs on GitHub

The new `.github/workflows/stage4h-full-answer-reference.yml`
downloads Qwen2.5 3B and Llama 3.2 3B into an isolated CPU
GitHub runner with `OLLAMA_NO_CLOUD=1`, loopback-only inference,
read-only GitHub permissions and no secrets.

Both reviewer models independently classify each of the **16
pre-authored sentences**, producing 32 real-model inference requests.
Neither reviewer sees source oracle labels, expected citations, case
IDs, questions or the other's votes. The complete-answer decision
requires **all** sentences to be accepted and full expected source
coverage. A malformed/missing review is **unscored**, not treated as
a correct negative or zero false-acceptance rate.

The report aggregates:
- per-model sentence false accept and false reject counts;
- per-model accepted inadequate, unsafe or adequate answers;
- reviewer disagreements and two-reviewer consensus decisions;
- answer-level fabricated-cause acceptances, good-answer rejections
  and incomplete-answer acceptances;
- evidence completeness, valid reviewer responses and model errors.

Output has fixed-key counts only: no raw prompts, answers, source IDs,
timestamps, model response objects, household names or network details.

## What the result CANNOT establish

- **These answers are prewritten reference fixtures**, not the seven
  exact Qwen-generated sentences from Stage 4G. A good Stage 4H score
  does not establish Stage 4G's actual prose is correct.
- The host-authored synthetic reference labels have not been
  authenticated independently by a second human reviewer or measured
  against true home event histories.
- Acceptance or agreement by one or two model judges is not a
  proof of meaning. False accepts and false rejects on this
  tiny corpus are only initial diagnostic rates.
- There is no review of independent model planning, choice of MCP
  tools, temporal reconstruction, actual smart-home investigations,
  operational latency, or human-rated naturalness and clarity.
- This is **not** permission to change the live V3 publisher or
  expose raw user information to a GitHub runner.

## Next required gates

1. Full CI and actual two-model reference job must pass at exact PR
   head. Examine both false accepts and false rejects, not merely CI.
2. Create a separately consented, privacy-protected, post-generation
   adjudication route for Qwen's **actual** new answers, retaining
   independent reference labels that are not visible to judges.
3. Increase scope to multi-event narratives, earlier/later command
   sequences, source/collector clock differences, missing logs and
   attribution disputes. Review user-facing clarity separately.
4. Only then propose a reversible, explicitly approved read-only
   shadow comparison and, much later, a publisher switch if warranted.

No installed HA add-on update, Hubitat/HA connection, device write or
production code modification is required. Roll back by reverting this
additive source PR or disabling the Stage 4H workflow.
