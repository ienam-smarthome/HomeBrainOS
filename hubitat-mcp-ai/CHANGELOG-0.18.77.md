# HomeBrainOS v0.18.77 — General evidence-led reasoning and answer quality

## Goal
Move beyond hard-coded Rule Machine parser/claim-guard patches and improve HomeBrain's ability to **answer the user's actual question like a strong analytical assistant**: compare systems, distinguish what could happen from what did happen, explain evidence, articulate uncertainty, and recommend one decisive next investigation.

## Architecture changes
- Add reusable **question-first analyst contract** to the existing shared no-tools final-answer coordinator. In analytical requests, instruct the model to lead with the strongest supported conclusion, compare hypotheses or systems when asked, explain implications, and identify one meaningful evidence gap without repeating boilerplate.
- Add a domain-agnostic **objective coverage checker** for complex read-only answers. Check whether requested comparisons, possibility judgments and explanations are substantively addressed. An explicitly qualified unknown is acceptable.
- For an otherwise fact-validated answer that omitted the question, permit **one additional no-tools model revision** with fixed, safe repair instructions. Do not authorize new MCP calls or alter write confirmation safeguards.
- **Re-run the existing factual validator** on the revision; if a revision introduces a known factual/causal contradiction or still leaves the objective unanswered, return the previous validated draft. Preserve simple one-pass requests and do not run this check without actual successful current-turn read evidence.
- Add coarse, privacy-safe counters: `answer_quality_gaps_found`, `answer_quality_revision_rounds`, `answer_quality_revision_rejected`, `answer_quality_revision_incomplete`, and `answer_quality_revision_accepted`.

## Safety and scope
- No Hubitat changes. No widening of tool authority or background calls. No additional paid-model routing. This works with the user's configured free model.
- Quality review is **not** a replacement for evidence grounding, causal-claim validation, or the existing strict Rule Machine claim guard. A partial investigation may legitimately remain unresolved even after a useful conditional explanation.
- An answer-quality check is *not* a factual truth verifier. Better model reasoning still depends on obtaining sufficiently rich typed data from Hubitat.
- New tests cover cross-controller comparisons, explanatory and possibility questions, qualified unknowns, single-round performance for good answers, no-tools revision, privacy and factual-validator fallback.

## Next steps
Benchmark HomeBrain and Claude with **identical read-only source evidence** across several non-Rule Machine scenarios (energy, sensor correlations, scheduled jobs, network health, and controller interactions). Record factual accuracy, question completeness, hypotheses compared, unsupported claims, latency, and number of model rounds. Avoid treating longer text as inherently better reasoning.
