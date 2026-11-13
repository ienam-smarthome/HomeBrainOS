# HomeBrainOS v2 alpha.74 — native timed-action follow-through without command rewrites

**Date:** 13 November 2026. **Baseline:** alpha.73 (restored alpha.65 native delay execution, plus one read-only broad inventory recovery). **Installed first-answer acceptance:** pending. **Live device actions in development:** none.

## Original source-real failures

- A direct delayed block requested on a media device in installed alpha.73 found its separate native internet-control actuator after the one additional broad inventory query. An original successful `hub_get_device` receipt showed the actuator's `blockInMinutes` command; however the model stopped and requested unnecessary clarification between **after N minutes** and **for N minutes**. No `hub_call_device_command` receipt existed in that request. The native read also reported internet access blocked at the timestamp of that reading, no timed block active. The need to reopen access *first* to schedule a future block is a distinct potentially undesired state change and must never occur implicitly.
- Another alpha.73 request shortly afterwards indexed eight **prior** receipts but performed **zero in-request MCP calls**. The first model round printed a plan and the exact native `hub_call_device_command(..., blockInMinutes, ["2"])` invocation in the user-facing answer as prose, without actually dispatching it. This is not evidence that the command ran, was accepted, or scheduled a deadline. The original user had already issued a direct instruction.
- An uploaded native Cudy device log screenshot shows **a separate historical sequence**: at 11:55:37 a two-minute block was scheduled, at 11:57:37 it reached its deadline and the device logged internet blocked; at 12:03:37 the device logged internet allowed. These log events support the native driver timer having worked in that earlier sequence, but without a command initiator receipt they do not establish that either of the above later model responses caused it.

## General, bounded fix

1. Preserve existing alpha.73 source-based broad-controller discovery and the **original alpha.65 native MCP command path**; do not reinstate alpha.66–71 action-continuation, preflight or claim classifier machinery. The client never selects a physical target, device ID, native command, scheduler or action on the user's behalf.
2. For a **clear original device-action imperative**, if the model is about to finish without *any in-request native tool receipt* despite live device-read and ordinary command tools being offered, provide **one** internal model-led follow-through opportunity. Warn that archived prior receipts and a printed command plan are neither a fresh live reading nor authorization to act on stale state. Let the model make fresh native reads and independently choose whether a supported operation is appropriate.
3. The same single follow-through checkpoint is available when the model read an alternate controller detail **after** the alpha.73 broad-inventory recovery, but is about to stop with **no native write**. This directly addresses the unnecessary after-versus-for clarification. No new tool or approval is provided: normal live catalog, permissions, `before_call`, `confirm=true`, sensitive-device safety and origin user intent remain authoritative.
4. Clarify the original requested **TARGET, EFFECT and TIMING**: “block after/in N minutes” is delayed onset, not “block for N minutes” or a trigger when activity begins. A native delay command is preferred over speculative helpers. A currently **blocked** actuator is not an active pending timer; do not unblock it merely to manufacture a new delayed block. Ask a precise clarification if reallowing access would be a separate unrequested state change.
5. Native `hub_get_device`, `hub_call_device_command` and relevant original readback receipts remain the source of execution and verification; the UI must not treat a printed invocation as an MCP action. The checkpoint is one-time, with no second write attempt, no rule creation and no incident-specific device names.
6. Expose `action_follow_through_invoked` in Technical JSON. Existing `inventory_recovery_invoked`, `source_review_kind`, original MCP tool receipt arrays and alpha.65 action/outcome review remain unchanged.

## Synthetic regression coverage

- Direct imperative, eight prior indexed receipts, **first draft contains only a command plan**, zero MCP calls: one general follow-through opportunity, then original model-selected fresh actuator detail, one native timed block, and existing read-only readback of the pending timer.
- Alternative control surface found after broad recovery, native delay advertised, model intends to stop with a clarification: one follow-through can re-evaluate intent and normal native execution path.
- Already-blocked native actuator, with no scheduled block: do not silently allow or create a new timer; preserve that source-bounded limitation.
- Explicit read-only instructions, capability questions, unavailable writers, low remaining time and an already submitted write never trigger an unsolicited command.
- A model that still declines to call any tools after the checkpoint must report that no native change is verified; synthetic tests do not establish real cloud-model quality.

## Limits and live acceptance

All synthetic scripts are fictitious. They test only the structural opportunity, not that a real model will select the right native command, that a device accepts it, or that the router enforces it. Delayed **unblock** remains unimplemented and is not implied by `allowForMinutes` (immediate temporary access).

Run exact PR-head and postmerge CI before release. After installation, assess the FIRST natural-language timed action against original MCP receipts: source-corroborated actuator identity, exact `blockInMinutes` argument, one successful native dispatch, pending-timer state, and independent later event reports. Do not conflate the user's current request with earlier log events.

**V1, upstream MCP server, external Device Monitor, scheduled jobs, native Cudy driver, and Rule Machine remain unchanged.**
