# HomeBrainOS v0.18.294 — Stage 5 independent cloud investigation pilot

**Development stage: a read-only, synthetic-only investigation benchmark using the same configured primary Ollama Cloud account as HomeBrain.**

The first four Stage 4N scenario scores were 16/16 across predefined assertions, with all eight unsupported candidate conclusions rejected. Those are evidence-classification results, not a test of autonomous investigation. Stage 5 removes provided candidate conclusions and adds real sequential source choice.

## Stage 5A — Independent conclusions
- The model receives a fictional focal incident and a source catalogue only; gold labels and complete source records are withheld.
- After selected records are revealed, it writes its **own natural-language explanation**, lists explicit source-cited finding kinds, and states uncertainties. No fixed answer statements are fed to the model.
- The source scorer evaluates declared findings against the actual selected records and the withheld gold finding kinds. Unsupported citations, physical outcomes and causal leaps are identified separately. **The scorer cannot prove the authored paragraph true or exhaustive.**

## Stage 5B — Model-selected evidence investigation
- The model selects up to **two** sources, from four fictional candidates, before seeing their contents. The host reveals only the chosen synthetic records.
- The host compares these choices to withheld independent relevant-source labels and scores recall and irrelevant picks.
- This is a **two-round, at-most-two-cloud-request** test. There are no actual native MCP tools or live Hubitat/HA reads. The model is not granted permissions to issue further reads or writes.
- Four choices: lighting, heating, ventilation and mesh-plug connectivity. Each scenario has decoy sources, fictional IDs and deliberately incomplete causal/physical coverage.
- Max five completed 2-request tests per hour across this separate Stage 5 benchmark, and a 10-second cooldown between tests. Provider errors stop immediately without retries or local/household fallback.

## Stage 5C — Human-readable explanation and independent checks
- The dashboard shows the original model-authored explanation, model/elapsed time, what evidence sources it chose, relevance, host-backed cited finding counts and unproven/high-risk findings.
- Optional **clarity and usefulness 1–5** scores are local to the page, not submitted or persisted.
- Full-prose semantic proof is explicitly **NOT** performed. The typed citations can miss unsupported claims in surrounding free text. Human blinded review against frozen source data is still required before considering publication changes.

## Running it
1. Upgrade the Home Assistant **Hubitat MCP AI** add-on to **v0.18.294**.
2. Open the existing HomeBrain web UI from Home Assistant or a phone.
3. Expand **Stage 5 · Independent AI investigation**.
4. Start with **Light switched on unexpectedly**.
5. Confirm consent for **up to two** Ollama Cloud requests (uses existing Ollama allowance), then tap **Run independent investigation** once.
6. Review the unverified explanation, evidence-source choices and cited finding scores. Share the text/results for independent assessment; do not paste secrets.

## Safety and rollout
- No installed model routing, production publisher, live rule/agent, Hubitat or HA writes are changed. The previous Stage 4 benchmark remains available.
- The add-on's existing primary Ollama HTTPS endpoint and credential are reused; no extra account or GitHub secret is necessary.
- The new endpoint is same-origin and consent-gated. No household logs, real source/device IDs, history, or live MCP records are sent.
- All tests in GitHub CI use fake model transports and do **not** spend cloud allowance.
- A perfect Stage 5 score is not evidence of Claude equivalence, safety or full autonomous investigation. It is a bounded synthetic signal about model-selected evidence and declared source citations.

Rollback: revert this PR, restoring 0.18.293.
