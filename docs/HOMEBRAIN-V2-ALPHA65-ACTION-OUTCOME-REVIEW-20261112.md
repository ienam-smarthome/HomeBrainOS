# HomeBrainOS V2 alpha.65 — model-led action and outcome review

**Date:** 12 November 2026. **Scope:** V2 normal Ask model loop, after native write-capable MCP results. **Source-real installed verification:** pending.

## Source-real motivation (private review, not repository fixture)

An alpha.64 first answer to a delayed-control request sent `hub_call_device_command(on)` to an already-existing *helper virtual switch* instead of the intended target's advertised native timed command. The MCP receipt confirmed the switch turned ON, while the model announced that a countdown had started and promised to issue another command thirty minutes later. A subsequent read-only inspection reported no pending driver timer for the intended device and did not identify a known automation link. Bounded dependency and filtered rule reads did not prove the absence of all possible future actions. This is a general disconnect between **requested goal**, **selected write**, **accepted command**, **stored delayed task**, and **future observed effect**.

The earlier alpha.64 live capability-discovery improvement worked correctly. No more helper search tools or client-owned scheduler are required. This is not a missing timed-command implementation or evidence that the physical router is permanently unreachable.

## Change

1. Strengthen the normal model-facing action guidance to compare the user's **specific target, operation and time semantics** with the selected *advertised native* command **before** issuing a write. Prefer an existing native capability when it directly implements the requested timing; the name of a helper switch, rule, dashboard or flag does not prove that changing it implements the requested downstream action. Avoid speculative substitute writes or ungrounded future-action promises.
2. Extend the **existing** optional model-led evidence-sufficiency loop to include **action outcomes** after a native potentially state-changing MCP tool result. Eligibility is derived from the current live MCP tool call name/selected leaf/declared read-only annotation and receipt category, **not** from device labels, user phrase matching, elapsed time or any particular driver command. It does not rewrite the model's answer or select an MCP read.
3. The new `action_outcome` review prompt compares the original tool receipt with the user's requested goal and offers the already-advertised **read-only** catalog. The model can independently select proportionate reads (e.g. a current target attribute or relevant dependency). During review a second write is rejected, including correction or rollback of the first. No automatic retry, unapproved corrective action, new scheduler, or hidden home-specific rule.
4. Attach a bounded `client_action_receipt_scope` label to the model's copy of a native action tool result. It identifies the submitted top-level tool and selected leaf but explicitly provides **no independent effect evidence**; the original MCP payload remains authoritative. Private Technical JSON marks `possible_native_action`, not a verified physical state change.
5. Skip the **extra text-only final claim audit** for this action-outcome review. It already receives a targeted source-to-claim review, and earlier live first-answer drafts sometimes got more certain after a tool-free final audit. This avoids introducing a redundant additional model pass and does not change the existing reviews for causal or historical read questions.
6. Preserves all existing user confirmation, upstream permission, best-practice key, exact-device matching and uncertainty-safe no-retry controls. A *successful transport receipt* is not by itself proof of a completed physical effect, accepted server-side domain operation, delayed job or downstream execution.

## Synthetic regressions and limitations

Synthetic cases (fictional devices, no household data) show:
- A helper switch is switched ON and the model's initial draft incorrectly claims a future action. It then chooses a target read during the review and gives a source-calibrated answer; no additional write is dispatched.
- A fictional native timed command is selected with correct numeric minutes and the model chooses a fresh pending-deadline readback. Only one write is executed.
- Ordinary read-only questions do **not** acquire a gratuitous action-review round.
- A model attempt to execute a replacement write during the post-action review is blocked.

The tests demonstrate the **available mechanism** under scripted model choices, not improved autonomous cloud-model action selection. The first write remains model-selected: this change does not mechanically block an incorrect initial command. The live assistant cannot autonomously wake later to run a promised task without explicit server/device-owned scheduling verified by a native receipt. Treat lack of a timed driver state as missing source evidence for the intended operation, not exhaustive proof no other controller exists.

## Acceptance gate

After exact-head PR CI passes and alpha.65 is installed, use one **new**, uncoached, low-risk delayed-control request to a target with an advertised native timed command. Capture original private Technical JSON. Score whether the model correctly identifies the target and native command **before writing**, validates exact parameter semantics from the live tool schema, uses a server-owned delay rather than an unverified helper, and reads back a pending target deadline. Verify whether `source_review_kind=action_outcome` and review tools remained read-only. A pass in synthetic tests is not an installed pass; do not claim router enforcement from timer attributes alone. Avoid live tests affecting essential or household devices without explicit agreement.

Preserve V1, external Hub & Device Monitor, existing Rule Machine integration and the clean model-led V2 architecture. No client-side deferred execution, mandatory rule creation, repair write, or device-specific patch.
