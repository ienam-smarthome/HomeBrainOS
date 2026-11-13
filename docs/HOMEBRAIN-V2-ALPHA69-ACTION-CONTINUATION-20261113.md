# HomeBrainOS v2 alpha.69 — continue explicit ordinary device actions after discovery

**Date:** 13 November 2026. **Scope:** V2 native Ask action loop only. **Installed cloud-model first-answer validation:** pending. No live hub/router commands, device effects or user-specific identifiers are included in the change.

## Source-real failure

In a private alpha.68 first answer, an explicit immediate device-action imperative led to a narrow name-filtered media integration and a question asking whether the user meant audio mute or another setting. The existing optional **read-only capability-discovery** review successfully located a separately named network-control actuator for the same physical device. The final answer then asked "Shall I proceed?" instead of executing the requested operation.

The original successful MCP receipts showed a credible separate controller with switch=off, but the model did **not** retrieve that controller's actual command definitions or current explicit internet-access state, and did **not** send any write. It also inferred internet access from the switch value. Neither the state-to-effect mapping nor live network enforcement was independently tested. This is a general **explicit action stalled after successful discovery** problem, not a missing native internet-control command.

## Implementation

1. General prompt/safety-guidance clarification: a user's clear imperative for an **ordinary** operation is already the instruction to attempt that exact action. Do not ask again merely because a different *control surface* was discovered, provided the physical identity relationship and command are established. A differently named controller is not itself a fuzzy failure when it is corroborated by real native source data; an arbitrary similar label or assumed IP is still inadequate. The model must distinguish questions or read-only requests from execution intent and respect ambiguous targets, sensitive devices, writer-specific preflight and client authorization.
2. **Keep the existing capability-discovery review entirely read-only.** When its completed draft redundantly asks permission after an original explicit imperative, allow at most one **separate, model-led native device-action continuation** within the *same user request*. This is not a new user permission, review or scheduler and does not automatically call a tool.
3. Limit continuation tool exposure to read-only tools plus `hub_call_device_command` **only**. A late write must be single-device, not a batch, and must match a successful **original `hub_get_device` receipt returned in this request** for that exact device ID and advertised command. A supported command name is not proof that the actuator is the correct physical target: the model is explicitly told to corroborate physical identity before selecting it. A command from a detail receipt with missing capabilities is rejected rather than assuming no sensitive capability. Lock, garage, security and valve capability records cannot be late-written via this path. Other writers, especially Rule Machine creation, are never exposed.
4. The late command **attempt is counted before dispatch**. If an upstream permission, approval, validation, timeout or domain result fails/ambiguous, the path offers no second write; any remaining round may make only read-only observations. An upstream tool's explicit `confirm=true` and user approval mechanism remains authoritative. Catalog visibility or user imperative is not approval to bypass per-call confirmation.
5. The model can select a proportionate fresh readback after its single command attempt; the final answer must distinguish command acceptance, device-reported state, and independently unverified router/physical effect. No automatic retry, state restoration, proxy helper, UI auto-approval, extra command, or deterministic device-name mapping.
6. If the user's message is a question (e.g. "Can you...?"), has a read-only clause ("do not change anything", "without making changes"), the model cannot prove target identity/command from current sources, or the action needs separate approval, the continuation must not be used to silently change state. If no qualified source exists, ask the necessary clarification rather than guessing. An ordinary direct write that happens **before** any review retains its original behavior and existing evidence review.

## Fictional acceptance

Fictional unrelated-name media integration and controller records (not actual household IDs) exercise:
- explicit command -> narrow media discovery -> read-only controller discovery -> a second source-supported command-detail read -> one model-selected native command -> post-command readback -> answer;
- a capability question or imperative with an explicit read-only clause does not transition to write-capable continuation;
- missing same-request supported command detail blocks the late write;
- critical actuators cannot be late-written, no batch, no alternative rule writer, and no second write after a first attempt (including a domain-level failure);
- normal negative/causal review and authorization behavior remain unaffected.

These tests validate the mechanism under scripted model choices, **not** actual cloud-model first-try accuracy or router enforcement. The natural-language imperative detection is deliberately conservative; ambiguous or complex language may still require clarification, which is safer than a wrong write.

## Acceptance gate

Require green exact-head PR pilot tests, full release assurance and repository validation; merge only after all green, then verify push workflows on exact merged commit. Install alpha.69 and run one new, user-authorized ordinary action with original Technical JSON: verify that the model independently correlates the physical target and correct actuator, retrieves current native command detail, issues **one** write without redundant conversational confirmation, and checks the appropriate postcondition. Do not infer enforcement from a stale inventory switch alone. Any operation requiring a distinct approval remains separately gated.

**V1, external Hub & Device Monitor and Rule Machine writer are unchanged. No live device action is performed by the development PR.**
