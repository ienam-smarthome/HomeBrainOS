# HomeBrainOS V2 alpha.59 — mobile frozen-evidence AI Evaluation

**Date:** 12 November 2026 | **V2 only** | No V1, Hubitat automation, external recorder or normal Ask policy changes

## Why evaluate again after V1 versus V2?

There are **two different decisions**:

| Question | Earlier V1/V2 comparison | This V2-only experiment |
|---|---|---|
| What are we comparing? | V1 and V2 as complete assistants | First completed V2 draft against the *same draft* after V2 source review + final audit |
| Primary objective | Which implementation offers dependable overall first-answer quality, source coverage, actions, voice, safety and performance? | Do extra review rounds actually make V2's factual conclusions better, or just slower/more confident? |
| Evidence acquisition | Each assistant chooses its native tools/sources, so retrieval differs | Original successful and rejected MCP receipts frozen identically; **no tool calls** |
| What a result can establish | Relative end-to-end ability and readiness for Gate B, given enough fair cases | Benefit/harm of **text-only revision** on the same returned evidence |
| What it cannot establish | Why an individual draft changed | Whether optional review improves MCP tool discovery or makes V2 superior to V1 |

The previous comparison is **not replaced, invalidated or repeated**. V1 remains stable until end-to-end Gate B acceptance, including independently grounded, cross-domain first answers and safe-write behaviour.

Recent alpha.55–alpha.58 **same-incident** replays returned human scores 2/8, 6/8, 2/8, 2/8. These are regression observations, not independent statistical evidence. Alpha.58's first-answer stage trace showed that a definite unsupported inference already existed *before* the source review, was retained after an additional read, and became a still-unverified "likely external cause" after the final audit. The model used eight rounds and ~18.1 seconds server time. This raised an architectural question: **should V2 retain both optional reviews, only one, or neither?** Avoid more incident-specific prompt patches until there is comparative evidence.

PRs #1609 and #1610 implemented a local-only paired scoring ledger and a tool-free model replay CLI, but required a PC/command line. Alpha.59 brings the same experimental idea into the existing Home Assistant add-on so it can be initiated from a phone browser.

## Operator flow

1. Ask a normal **read-only** V2 question in **Ask / Chat**. This still uses the normal AI-chosen MCP investigation and captures its private Technical JSON. Alternatively, choose an older **private JSON file** using a phone's file picker.
2. Open **AI Evaluation**, press **Use latest Ask evidence** (or select the file), and inspect the selected source summary. The captured answer's previous model prose is NOT included as replay evidence.
3. Read and check the **explicit per-run consent**. The entire original MCP evidence set will be sent to the already configured model provider for three rounds. Cloud model services may expose this data to their provider and incur charges. Nothing is transmitted until the user selects Run.
4. The add-on performs one model-only initial answer, source-review continuation and final-audit continuation. It offers no tools, never calls MCP, does not repeat device history or issue device commands, and stores no evaluation file on the server.
5. The UI shows the initial and reviewed answers side by side, exposes the intermediate stage, the original successful/failed receipt counts, model-round count and latency. The operator can download **PRIVATE JSON** from the browser; everything is session-only unless they do.
6. Human reviewers independently score factual grounding, source completeness, causal calibration and usefulness (0/1/2 each; N/A for causality only when genuinely inapplicable). Source filter scope, row caps, issuer/reporter roles and missing discriminating reads must still be checked against original successful receipts. No AI output is automatically graded as correct.

## Implementation and safety limits

- **API:** \`POST /api/evaluation/replay\` requires the existing \`X-Homebrain-Request: 1\` browser request header and explicit boolean \`send_private_evidence_to_configured_model=true\`. A normal Ask does **not** automatically trigger evaluation.
- **Input:** private Technical JSON or \`homebrain-v2-frozen-receipts.v1\` packet; <=1 MiB total and <=240,000 serialized receipt characters. Requires one or more original successful reads, refuses unverified failed executions, read/write tool names, hidden prior conversation receipts and incomplete source payloads. Oversized results fail instead of silently truncating.
- **Execution:** uses only \`Agent.round(messages, tools=[], remaining)\` from the configured model, and the repository's existing review prompts. It shares Ask's model-use lock. Extra unsolicited model tool requests are rejected; no such tool call is executed. A model failure rejects the comparison rather than emitting a misleading partial "improvement" verdict.
- **Privacy:** the evidence and resulting answer text are held only in the request/browser memory (as with Ask), not in an evaluation database, logs or the external recorder. Existing no-cache policy remains. Exports intentionally marked PRIVATE. Cloud data transmission **is not prohibited** if the user consents; a cloud provider can see the raw captured evidence.
- **Meaning:** this tests *review text revision* from a common initial draft, not independent repeated runs, not probabilistically unbiased A/B, not a live test of alternative tool retrieval, and not a direct V1/V2 comparison. Stronger evidence requires fresh independent questions, multiple repetitions and blinded human ratings.

## Acceptance path

CI syntax, Python contract tests, browser UI, package smoke test and release assurance must pass before merge. Install alpha.59 only if green. Then collect at least **12 fresh cross-domain, uncoached read-only first answers** (causal devices, heating/sensor history, power and stored samples, native rules, system health and sparse data) and repeat the two conditions with blinded scoring. Keep the old causal regression incident separately. Record model version, elapsed time, scores and unsupported definite claims. Decide whether review prompts add net benefit without modifying source selection on the basis of an anecdote.

**No live/private household test evidence is committed to GitHub. This feature has not yet run against the user's configured model merely because it exists in source code.**
