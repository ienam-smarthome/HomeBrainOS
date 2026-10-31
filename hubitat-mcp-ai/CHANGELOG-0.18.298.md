# HomeBrainOS v0.18.298 — Stage 6.3: investigation completeness and evidence-value stop audit

**Scope: Stage 6 experimental fictional evidence benchmark only.** The normal HomeBrain agent, runtime publisher, Home Assistant and Hubitat integrations, device controls and routing remain unchanged.

## Field failure that motivated this release

The real Gemma4:31b Cloud Stage 6.1 clock-conflict retest correctly reconstructed E2/E3 source timestamps with **13/13 declared source-value atoms verified** and **zero source-type mismatches**. However, it voluntarily stopped after reading S2 and S3 despite S1 (application brightness command history) still being available. Its justification that "no remaining sources provide light state data" was too narrow: a command record could have changed the explanation without being a state report.

This is an **evidence-completeness and stopping problem**, not a source classification problem.

## New general mechanism

Before deciding READ or STOP, Gemma must reason from the original question, list up to four unresolved investigative questions, and assess the potential contribution of **every unread source title**. Each entry declares whether it could materially change the answer and why.

New v2 plan structure:

- `schema: homebrain-stage6-next.v2`
- `action: read | stop`, plus `source_id` (null on STOP)
- `reason`
- `open_questions`: up to four specific unresolved questions
- `source_evaluations`: one entry per unread title, with `source_id`, `could_change_answer` (boolean) and a specific `why`.

The host validates that every unread source was assessed once, the chosen READ source was marked potentially useful, and the model **does not STOP while its own assessments flag a potentially useful unread source**. Inconsistency is rejected without retrying or silently selecting sources on the model's behalf.

This policy is **domain general**: it considers what might help answer the user's question, not keyword-triggered lighting or an S1-specific exception. No withheld gold labels, expected source IDs or required findings are sent to the model.

## Honest limitations

- **A model can still be wrong about usefulness.** If it marks an important unread source "low value" and stops, the benchmark continues to report the resulting source-recall and expected-finding gaps. The new source-value ledger makes this error inspectable; it does not prove completeness.
- Passing the ledger's structural consistency check does not prove the human-readable explanation true.
- Legacy v1 planning responses remain readable in offline regression/mocks, but the dashboard explicitly warns that they were **not fully audited**. Live model prompts request v2.
- No hidden gold labels are used to compel an extra read or inflate evidence discovery scores.
- The final answer receives the titles of unread sources plus the model's latest unresolved-question ledger, but **not** their record contents. This permits transparent uncertainty without fictitious command claims.
- Stage 6 continues to use at most **four explicitly consented Ollama Cloud requests**, up to three fictional source reads and one response; no retries or extra cloud calls were introduced.
- Independent full-prose meaning and causation are **not certified**. Stage 6.1 exact-value/provenance checks and the v0.18.297 no-inference Cloud connection diagnostic remain present.

## How to verify from your phone

1. Update Hubitat MCP AI in Home Assistant to **v0.18.298**.
2. Open **Stage 6 · Conflicting evidence**, choose **Delayed OFF report versus device time**.
3. Explicitly approve up to four requests from your existing Ollama Cloud allowance and run once.
4. Expand **Unanswered questions and per-source value assessments** and **Read sequence and sentence-level source checks**.
5. A stronger investigation will consider the relevance of the command-history source S1, ideally inspect it as well as S2/S3, and explain why receipt order differs from source-event order without claiming actual hardware state changes.
6. If it still stops at two sources, examine why the model marked unread S1 low-value: that is genuine model decision quality, not a reason to weaken validation.

**CI** uses mocked cloud models only. It tests 3/3 source coverage, an internally contradictory STOP that must fail, and an internally consistent but actually incomplete STOP that must remain visibly incomplete. No live account calls or device reads take place during CI.

Rollback: revert this PR and restore v0.18.297.
