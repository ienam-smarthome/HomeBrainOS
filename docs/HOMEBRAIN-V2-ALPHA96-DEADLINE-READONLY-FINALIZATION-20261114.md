# HomeBrainOS V2 alpha.96 — deadline-aware read-only causal completion

**Date:** 14 November 2026. V2 Preview only. This changes the existing model-led response lifecycle and is not a physical hub-load diagnosis.

## Private acceptance evidence

An installed V2 alpha.94 long-running causal investigation visibly reached the 300-second request limit after 20 displayed tool attempts (one shown unsuccessful) and returned an Ollama Cloud model timeout instead of a causal answer. The attached screenshot does NOT include the original receipts or per-round timing for that long request; no claims are made about the exact successful native source count, source coverage, device chronology, service responsibility or cloud cost. Separately, an alpha.94 simple current-state question succeeded after one rejected and one successful `hub_list_devices` call in 19 seconds and three inference rounds; the device-level `lastActivity` did not timestamp its individual current attributes. Neither capture validates a new live model improvement.

## General improvement

A long read-only causal investigation with already-retrieved native receipts should reserve enough of its existing time budget to produce a qualified answer, rather than keep requesting tools until there is no model-answer time left.

At the **start of an already-scheduled model round**, only when all these conditions hold:
- The configured request deadline is at least 120 seconds, and the remaining time is positive but at most `min(75, max(35, deadline_seconds * 0.25))` seconds.
- The model is handling a general causal investigation and there is at least one **successful native read-only tool-result receipt**.
- All actual tool attempts in this request are in the existing allowlisted read-only family, with **no** successful native action, pending action prewrite reconsideration, or automation confirmation.
- The existing source-to-claim final audit is not already tool-free and the deadline finish has not already run.

...the existing next model round receives **zero tool definitions** and a concise instruction to finish from original available receipts, report actual source time/row coverage and failed reads, distinguish the reporter from issuer and avoid unsupported causes. This selects no tool or cause, makes **no additional inference round**, issues **no more native MCP calls**, and never fabricates an evidence summary on behalf of a failed model.

If the provider refuses to finish, times out, returns an empty answer, or asks for unoffered tools, preserve existing original receipt/error evidence and fail explicitly. Tool requests from the tool-free finishing round are **never dispatched**. The existing native approval path, write permissions, provider choices, initial MCP failure reporting and V1 are unchanged. This is a best-effort latency/reliability improvement, **not a guaranteed completed answer or a speedup**.

## Synthetic verification and installed acceptance

New fully fictional tests require one successful native read-only source then advance a synthetic clock into the reserved window. Assert one existing final model round with no tools, zero extra MCP calls, a qualified completed answer, and denial of a model-proposed unsolicited write. A noncausal status request must not trigger forced deadline finishing.

Require all existing V2 metadata, UI, security, source-contract, container and Python CI checks. Once hub stability is independently confirmed, compare a genuinely new source-real first answer with original receipts; record actual number of read-only source calls, failed sources, provider model rounds, latency, cutoff invocation, result and any unsupported causal claims. A failed model may still fail this gate. Do not replay the already-exposed test as a new blind quality sample or treat a synthetic pass as model intelligence.
