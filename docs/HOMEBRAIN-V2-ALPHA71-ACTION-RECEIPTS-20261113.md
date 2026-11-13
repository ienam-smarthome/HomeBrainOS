# HomeBrainOS v2 alpha.71 — receipt-grounded device dispatch and outcome reporting

**Date:** 13 November 2026. **Scope:** V2 Ask device-action lifecycle, model guidance and Technical JSON only. **Installed live acceptance:** pending. **Live device effects in development:** none.

## Original source-real failure

In an alpha.70 installed first-answer capture, the model correctly discovered the separate actuator for the original user-requested effect and read its supported command plus initial blocked state. The model's first `hub_call_device_command` was **rejected locally**: no native command was sent because the alpha.70 continuation requires a **new successful `hub_get_device` receipt after entering action continuation**. The code nevertheless consumed the one permitted write attempt BEFORE checking this preflight. The model obtained the missing detail read and submitted the same command again, but it was rejected by the one-attempt gate. **No command reached Hubitat; no later target-state readback proved success**, yet the final answer claimed the action completed. Both failed calls were zero-millisecond local rejections, not an error by the upstream Hubitat server. The physical state at capture was source-reported blocked; no later independent router state was checked.

## Correction — source-grounded lifecycle, not an incident-specific action path

1. Retain the alpha.70 general model-led physical target/control-surface discovery and one single-device command continuation, including same-request detailed command receipt, critical-device refusal, independent source selection and original native permissions.
2. Keep a local evidence-preflight rejection distinctly identified by `dispatch_state="preflight_rejected"`, `operation_executed=false`. It **does not consume** the one permitted *native dispatch*; the model may use native read-only tools to correct the missing detail and then choose one supported ordinary native device command. Cap local preflight corrections to prevent looping. No client-selected command, automatic retry, alternative device or scheduler is introduced.
3. Mark `action_continuation_write_attempted` and `action_continuation_dispatch_attempted` **only at the actual native MCP dispatch boundary**, after local catalog, evidence and approval checks have passed, immediately before `mcp.call`. Any timeout, transport error, domain rejection or ambiguous result after this point permanently disables further write attempts for that request. If user approval was declined/failed, the attempt is closed without dispatch: never try another route or writer.
4. The original native command receipt and model-visible result record preserve `dispatch_state` and distinguish `preflight_rejected`, `approval_denied`, `native_result` and `outcome_unknown`. Technical JSON exposes a **source-derived** `action_receipt_status` (e.g., not attempted, pre-dispatch rejected, native accepted, native rejected, submitted unconfirmed, outcome unknown) separately from any matching native waitFor/readback. A top-level `success=true` is still only answer completion, not a device-effect guarantee.
5. Add a narrow, generic **fail-closed final claim guard** for clear device-action requests with original command receipts. If the model asserts it executed/completed a change but there is no actual native dispatch, a source-reported rejection, or a submitted but unverified outcome, replace that unsupported claim with a receipt-grounded, explicitly limited status. If a source-reported native acceptance and a matching native postcondition are both present, preserve the model's normal answer. This is not an incident-specific natural-language device rule: it applies across all single-device commands and does not decide target, tool or action.
6. Do not equate command submission, acceptance, native source-reported state, and physical/router verification. Even a converged waitFor is an observation from the native source, not proof of independent real-world enforcement. A failed waitFor does not necessarily mean the command was not accepted; report both independently.

## Fictional regression coverage

- Exact class of failed alpha.70 sequence: original imperative -> media read -> model-led read-only alternate actuator discovery -> one **pre-dispatch** `hub_call_device_command` rejection for absent NEW detail -> fresh `hub_get_device` -> **one accepted native dispatch** -> readback matching requested attribute; claim preserved when source-backed.
- No post-rejection detail: model falsely says it completed a task -> guarded answer explicitly says **no native command sent**.
- Native domain response `success=false`: no false successful-effect claim.
- Native `success=true` without verified readback: accepted submission but not a verified changed state.
- After native timeout, a second write attempt is forbidden; outcome remains unknown.
- User-declined approval is not circumvented by retry or alternate action.
- Nested original MCP text receipts preserve reported acceptance independently from a timed-out waitFor.

The synthetic tests verify the client state machine and model choice path, not model reliability or physical router behaviour. No private home device identifiers or private MCP response payloads are checked into the repo.

## Acceptance

Require green exact-head v2 pilot suite, release assurance, repository validation and post-merge checks. Install alpha.71 and run a new user-authorized ordinary device action; assess source-real Technical JSON for correct controller match, **one native dispatch**, `action_receipt_status`, fresh native state readback (or explicit uncertainty), no unsupported “done”, and no double write. No real-device changes are made by the PR.

**V1, external Hub & Device Monitor, Rule Machine/Visual Rules writer, and upstream MCP server are unchanged.**
