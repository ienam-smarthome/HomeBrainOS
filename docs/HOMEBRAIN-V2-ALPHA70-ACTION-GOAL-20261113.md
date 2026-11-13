# HomeBrainOS v2 alpha.70 — action-goal completion and source sufficiency

**Date:** 13 November 2026. **Scope:** V2 Ask model-led source review and bounded device-action continuation only. **Installed first-answer acceptance:** pending. **Live device actions in development:** none.

## Private source-real failure

An alpha.69 first-answer request expressed an **explicit, immediate device action**. The model performed two successful read-only calls: a narrow label-filtered inventory (one match out of a much larger total) and a detailed read of that media integration. The media record reported connectivity and audio attributes but not the requested network-access effect. The model concluded by asking what the user meant, rather than investigating potential separate control surfaces. No action was attempted. In the original Technical JSON, `source_review_invoked=false`, `action_continuation_invoked=false` and `action_continuation_write_attempted=false`.

Alpha.69's optional capability review and continuation depended on particular **draft wording**: an unsupported-capability denial or "Shall I proceed?" prompt. A clarification draft bypassed both, despite the same original action goal remaining unresolved. This is general goal-completion gating, not a need to hardcode a particular physical device, word or driver.

## Implemented correction

- For a clear, permitted **imperative**, the existing one optional model-led source-sufficiency review now becomes eligible when the assistant is about to complete the first answer and **no native write has been attempted**, independent of the draft's wording or its claim that an action was completed. The original question is the specification; no fixed device tool, search query or command is chosen by client code. Time headroom and availability of read-only tools still gate the checkpoint.
- Introduce an `action_goal` **read-only** review prompt requiring model comparison between the desired effect, physical identity and actual returned source scopes. A name-filtered media record with online/unmuted status does not establish an unrelated network, power, heating or security effect. The model independently chooses whether broader discovery, alternate actuators, identity corroboration or detail reads can resolve the goal, or reports genuine uncertainty if not.
- Reuse alpha.69's separately gated, same-request single-device command continuation for *either* `capability_discovery` or `action_goal`. **Continuation eligibility is not conditioned on "Shall I proceed?"**. Only an original direct imperative (not a question/read-only instruction), no prior native write attempt, permission-relevant live writer presence and sufficient time can offer the continuation.
- Retain strict scope: the discovery phase offers **read-only tools**. A follow-up action phase offers only read tools and **one** `hub_call_device_command`, never rule writers or batches. A late write additionally requires a **new successful native `hub_get_device` detail read after entering the continuation**, advertising the exact device ID and command. A pre-review media detail cannot silently authorize a different controller. Unknown/critical capability classes are rejected, the model must corroborate physical identity, and existing explicit `confirm=true`, token access and user approval rules remain authoritative.
- Count the write attempt before native dispatch, including if later rejected, failed or timed out, so there is no second write or automatic correction. The model may perform read-only outcome verification and must separate the hub's command acceptance from target-state readback or physical effect. If a request is already satisfied, genuinely ambiguous or forbidden, the model must not perform an unnecessary action.
- Technical JSON preserves the original MCP receipts, the pre-review draft, `source_review_kind="action_goal"`, and existing `action_continuation_invoked` / `action_continuation_write_attempted` flags. No separate review layer, background scheduler or hardcoded device mappings are added.

## Fictional regression coverage

A fictional screen's narrow media integration reports online/unmuted but lacks the requested access-policy capability. The scripted model's **clarification draft** now triggers the action-goal review even though it is neither a capability denial nor "Shall I proceed?". The model chooses a broader inventory, inspects a separate source-corroborated controller, and uses the existing bounded continuation for one advertised command and a fresh access-state readback. Tests verify no direct writer during read-only review, only one write after a new detail receipt, and no automatic retry or unauthorized unrelated command.

Additional tests check a falsely optimistic "Done" draft with no native receipt, a legitimately unresolved identity that remains read-only, a stale media-detail attempted write that is rejected, capability questions and explicit read-only requests, and no continuation after an already attempted native write. Existing synthetic tests are adjusted to distinguish **capability questions** from actual imperatives.

**Limitations:** These are scripted model choices and source-bounded eligibility tests. They do **not** establish that the installed cloud LLM will discover the correct controller first time, that the actual client can write, or that router/physical state changes. No user-specific device ID, network identifier or private MCP receipt is retained in the repository.

## Release and installed acceptance

Require green exact PR-head v2 pilot tests, full repository validation and release assurance before merge; re-check all merged-commit workflows. After installation, separately authorize a natural ordinary device command and review the **original** Technical JSON: Did the model use the action-goal review, discover source-supported controller identity, inspect the actual command, submit no more than one write and read back a relevant attribute? An unavailable or ambiguous controller must produce a calibrated question/limitation rather than an invented effect. Preserve all confirmation safeguards.

V1, external Hub & Device Monitor and current native Rule Machine authoring are unchanged.
