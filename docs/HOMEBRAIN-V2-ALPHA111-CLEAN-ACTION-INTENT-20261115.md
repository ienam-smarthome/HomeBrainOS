# HomeBrainOS V2 alpha.111 — source-preserving action retry

**15 November 2026 — V2 Preview only.** This public engineering note intentionally excludes private device names/IDs, IP addresses, tokens and original MCP receipts.

## Installed failure

An ordinary ON/OFF instruction received a ten-second text-only "No action queued" response. The user selected **Prepare action**. The web UI concatenated a long generic retry instruction including the words *read-only device evidence* into the original user prompt. A second request eventually submitted a native command, accepted by the original MCP result, but its terminal `action_lifecycle.status` was `not_applicable` despite `native_write_submitted=true`. The conservative imperative classifier checks the *entire* question for read-only prohibitions: the UI's appended instruction changed classification. This is a request-intent and presentation defect, not independent evidence of a failed device action.

The second request took ~21.4 seconds, six paid model rounds, ~12.16 seconds provider-reported model time, ~6.55 seconds native tool attempts including ~2.25 seconds human approval waiting, and ~290k provider-reported input tokens. These numbers are descriptive and **not** an exact additive wall-time partition. Earlier reported ~5-second performance is a user observation; an identical baseline with original receipts is unavailable. The prewrite-model checkpoint and the additional action-outcome review can add model rounds; this patch **does not remove them** or claim to restore a five-second response.

## General V2-only correction

- Each new Ask/Speak remains an independent conversation with empty history. **Prepare action** re-submits the *unchanged original user question* and a discrete `prepare_action` boolean. Bounded guidance is added in the model system context only when the original question is a directly recognised imperative. It is not an instruction from the user, does not choose a target, select or dispatch a native command, approve a write or reinstate old source evidence. A typed one-word *proceed* while an unqueued card remains visible starts a **new** preparation; it never approves or retries a previous selected/uncertain native write.
- The final "No action queued" answer and card are shorter. Original tool receipts and performance counters remain in the PRIVATE Technical JSON. When a genuine native write was submitted, the lifecycle classification is still driven by original MCP acceptance and transport submission, not the model's prose.
- No changes to the existing source/identity checks, prewrite model review, native permission gate, real Approve/Edit/Dismiss, cancellation, no-retry policy or V1.

## Acceptance

Synthetic FastAPI tests require the exact original question and separate new preparation signal. Browser tests require a fresh conversation, empty history, no appended retry text and no approval replay. Existing prewrite/native approval, history and cancellation tests must stay green. This patch cannot be called a first-answer efficiency improvement until source-real installed comparison: for an uncoached low-risk action capture original read/write receipts, explicit approval, accurate `action_lifecycle` and actual model/tool/human latency separately. Verify physical state independently where it matters.

**Next performance milestone** after safety-gated live confirmation: measure which redundant model rounds can be safely removed or replaced with a source-verified terminal receipt summary across diverse simple actions. Preserve strict approval/identity and avoid a device-specific shortcut. Roll back this PR if separate retry guidance affects model intent, permissions or selected native tools.
