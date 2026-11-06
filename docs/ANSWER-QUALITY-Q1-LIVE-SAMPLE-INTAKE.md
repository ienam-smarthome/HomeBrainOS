# Q1 single-response intake — no invented answer scores

**Purpose.** Prepare one privacy-safe, observational Q1 packet from a user-supplied
HomeBrain **read-only** answer's complete Technical JSON. This provides a
reproducible starting point for independently reviewing the *actual answer*
against source values. It is not an automated correctness judge.

## Next registered case

Case: `multi_device_named` from the unchanged 13-task legacy
catalog. Submit exactly once in a **New topic** after confirming the installed
HomeBrain add-on version:

> Compare the states of Hallway Light 1 and Livingroom Light 2.

Provide the full natural-language answer and full Technical JSON **privately**
in the chat. No Hubitat, HA or router state changes are authorized. If the
system asks for confirmation of a write, do not approve it.

## Intake (offline, only when capture is available)

```bash
python scripts/answer_quality_live_sample.py \
  --case multi_device_named --receipt /private/answer.json \
  --output /private/summary.json
```

This tool reads the raw JSON locally and writes an intentionally restricted
summary: frozen-case ID, API-prompt digest equality (not the digest itself),
reported version/model, elapsed and provider timings, tool/read/write counts,
transport outcome, and completeness limitations. It **never** emits the
natural-language answer, exact device IDs, raw tool arguments, local IPs,
private log text or authentication tokens. Store full source/answer evidence
privately for independent review; the scorecard must not consume this summary
as an automatically graded review.

The registered-question hash is computed with the production
`collapse-whitespace-v1` normalization: strip, split whitespace,
join with one ASCII space, then SHA-256. A matching hash authenticates only
the question supplied to the **API**, not model delivery. User-reported
`first_attempt_verified`, `deployed_build_sha_verified` and
`model_delivery_verified` flags are **not** independently
attested; even if one says true, the script leaves official
first-attempt accuracy **not measured**. `success=true` is
transport completion, not answer correctness or a physical-device result.

A read receipt shows a source method was executed, not whether the final
answer quoted the right source value or covered the whole question. A
human reviewer still checks the answer, direct read values, recency, source
scope, causal certainty, possible unsupported explanations, and extra calls.
Only then may a separately reviewed entry be added to
`scripts/answer_quality_scorecard.py`.

**No Q1 first-attempt accuracy or Claude-comparison percentage is available
until independently source-reviewed complete responses exist.**

## Relation to the successful timed Internet project

The separate Nov 4 driver-timer acceptance on two distinct Internet-control
devices verified a scheduled block-report for each and a faster initial
v0.18.399 confirmation step. This is **functional/device timing evidence**,
not an answer-quality benchmark or proof of physical endpoint connectivity.
The 07:00 driver auto-cancel setting, reboot-missed-job recovery and
multi-device/cancellation live tests remain separate acceptance topics;
no additional Internet-specific patch is implied by this Q1 milestone.

## Supplied live result — 6 November 2026 at 12:57 UTC

The requested `multi_device_named` read-only question, natural-language answer,
and complete Technical JSON were received privately. The response reported
HomeBrainOS `0.18.427`, Free Ollama Cloud `gemma4:31b`, 7,069 ms
end-to-end elapsed, 7,003 ms agent, 4,021 ms provider,
3 model rounds, 4 total tool calls, and zero writes or confirmations.

The independently calculated registered-question fingerprint agrees with
`request_provenance.normalized_prompt_sha256`. All **four** published
Hubitat-reported switch/retained-level values agreed with matching typed
targeted resolver receipts. The two other targeted list reads were discovery
evidence, not independently sufficient to support the four final values.
Neither reporter source nor a retained brightness level proves physical
connectivity, actuation or attribute-change time.

**Do not reinterpret this as a formally scored first attempt:** the response
explicitly declares model delivery, first-attempt status, and deployed Git SHA
unverified. A single 7.069-second observation is below the nominal 15-second
common-status target but does not establish median, p95 or cross-version speed
change. The captured final answer is source-consistent; this does not authenticate
the first unaudited zero-tool model draft. No raw private device names/IDs,
answer transcript, source payloads or request hash are committed here.
See [dated handoff](ANSWER-QUALITY-STATUS.md) for the evidence-bound review.
No repetition of this live question is needed. Continue Q2 fixed-evidence
human source reviews before claiming measured model improvements.
