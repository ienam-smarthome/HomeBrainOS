# HomeBrainOS V2 alpha.117 — bounded routine post-write native state read

**15 November 2026. V2 Preview only.** No private IDs, labels, addresses, tokens or original household MCP receipts are published here.

## Live source and question

Two installed alpha.116 source-real simple lighting actions achieved the first accepted **no-extra-approval** workflow: OFF 4.492 s (server 4.398 s) and ON 6.138 s (server 6.070 s). Each used one cloud model round and 1,400 provider-reported input tokens, fresh direct device and separately verified bridge source data, a genuinely native accepted write, and 0.88/0.75 **milliseconds** spent in the no-card approval gate. The original native command result had an embedded OLD state (ON for the OFF write; OFF for the ON write), which was correctly not treated as a post-write state or physical proof. Neither request independently checked state afterward. The first OFF request's later reported state timestamp preceded the client-side estimated write submission, making causal reconstruction inappropriate. The charter's common-control latency target is under 15s median and p95 across comparable samples; two successful requests cannot establish those distributions.

The owner explicitly asked for one lightweight follow-up read to improve state reporting and a full project aims/scope assessment. This milestone addresses only the **generic routine write outcome source contract**; it does NOT change any model tool selection, confirmation class, upstream write permission, automation or history logic.

## Implementation

- On the interactive V2 path only (legacy V1 and standalone Agent tests unchanged), **after** the model-selected routine native writer has returned a matching original success/acceptance, perform at most **one** read-only native `hub_get_device` on the *same model/source-verified target*. Timeout is limited to **1.35 seconds**, with a deadline guard; no polling, no state mutation, no model round and **no retry of a writer**.
- Original source record is retained separately and marked `client_routine_post_write_readback=true`. Independently match returned ID and label; require an unambiguous original switch attribute, even if presented via attributes/currentStates. Source success alone does not establish correct state.
- A separate read returning the requested state is reported as **Hubitat subsequently reported ON/OFF**. A differing state is reported as **not confirmed**, not as a failed physical light, and unavailable/mismatched/inconclusive read retains the truthful native acceptance boundary. A read is independent of the *write-response snapshot*, not independent evidence of the real-world physical effect or its initiator.
- Capture `first_native_write_submission_elapsed_ms`, **new** `first_native_write_response_received_elapsed_ms`, and **new** `routine_readback_started_elapsed_ms`, `routine_readback_finished_elapsed_ms`, `routine_readback_elapsed_ms` from the **same local monotonic request origin**. Do not compare these offsets with Hubitat's device event wall timestamps as if they were the same clock. Preserve provider-reported model timing as nonadditive.
- Full PRIVATE Technical JSON includes `routine_action_fastpath.post_write_readback.status` (matched/not_matched/identity_mismatch/state_unavailable/read_unavailable/not_invoked/deadline_insufficient), reported value, elapsed, and `physical_state_verified=false`. The separate source row is present in tool_calls when attempted.

## Scope and evaluation consequences

This addition raises potential answer completeness for immediate writes, but it does not solve broader V2 model-led historical evidence recovery, causal explanation, native one-off automation validation or unseen-case first-answer accuracy. The original project direction in `docs/ANSWER-QUALITY-CHARTER.md` requires >=90% grounded conclusions, >=80% useful first answers, zero unsupported definitive causes and <15s common status/control latency across a representative reviewed set. The repository describes a 53-case *definition* inventory but does not provide a human-graded full-suite production success rate, matched Claude gap or defensible p95. Do not count synthetic CI as those results.

Synthetic fictional regressions verify matching/mismatched state, read timeout/error, wrong identity, contradictory attributes, fail-closed source handling, exactly one original native write, real existing consent gate, no extra model round, monotonic phase order, and no read after rejected native write. No real MCP commands or paid provider calls occur in CI.

## Installed acceptance and rollback

Update V2 Preview alpha.117 only after exact-head CI green. In one new eligible simple ON/OFF request, verify that the original writer was accepted, **then** a separately marked native `hub_get_device` read appears, with truthful match/mismatch/unavailable outcome and no second AI round. Compare latency against 4.5s/6.1s alpha.116 observations while distinguishing device read overhead and provider/model time. A later Hubitat state observation remains **not physical proof or definite cause**. If the read slows >1.35 seconds, changes original write/permission rules, triggers duplicate writes or makes unsupported physical claims, revert this opt-in code and retain alpha.116.
