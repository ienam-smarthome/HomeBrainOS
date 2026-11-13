# HomeBrainOS v2 alpha.73 — source-complete control-surface discovery with restored timed blocks

**Date:** 13 November 2026. **Baseline:** alpha.72, the alpha.65 functional rollback. **Installed first-answer acceptance:** pending. **Live effects during development:** none.

## Source-real regression motivating the change

The restored alpha.72 live request asked for a delayed internet block on a media device. The model read a narrow label-filtered inventory and details for that device's media integration, then incorrectly asserted that network-level blocking was unavailable. Earlier original MCP receipts had established a **different managed actuator** for that same physical device that exposes native delayed blocking. The first source-real success on the alpha.65 baseline involved a separate media target and verified `blockInMinutes(2)` with a pending block and later enforcement. This is evidence of a native delayed-block capability and one historical live success, not proof that all targets are identified reliably.

The consistent failure is **filtered source coverage**, not broken native delay execution. The user's distinction remains important: delayed **block** was working; delayed **unblock** was not. The driver advertises an immediate temporary allow and an immediate allow, not a verified native allow-after-N-minutes operation. We do not claim to implement delayed unblock here.

## Change — one generic read-only coverage recovery, never a command router

- Keep the alpha.65 `agent.py` native MCP write path and original action/outcome read-only verification untouched. Neither the upstream MCP tool schemas nor the timed-block command syntax or scheduling logic is replaced.
- If a **clear imperative device-action request** is about to complete **without any native write attempt**, after one or more successful **filtered** `hub_list_devices` searches and **no broad inventory**, and sufficient time remains, perform exactly **one** additional source-real `hub_list_devices(format="context")` READ-ONLY query with *no device/room/capability filters*. This is a coverage safeguard, not an inference about a target, a device-specific heuristic or a command. Query/source failures are reported and never interpreted as proof that no controller exists.
- Return the original MCP result in the Technical JSON as a separate `hub_list_devices` receipt (`client_inventory_coverage_recovery=true`, `read_only=true`). Feed the result to the connected model as **untrusted source data**, along with general instructions to compare the user's intended physical effect and timing with possible *other* control surfaces. The model independently selects any candidate, reads its actual commands, verifies physical identity and chooses **whether** to execute a supported native command.
- Do not run this broadening after a native write was already attempted, when a prior broad inventory exists, for capability *questions*, read-only or dry-run requests, without available `hub_list_devices`, during an already active source review or with insufficient deadline headroom. No backtracking/retry/undo after possibly executed native commands.
- The existing per-call confirmation gates and ordinary single-device native command path remain authoritative; critical or ambiguous targets must not be guessed or controlled merely because a related label appears.
- Expose `inventory_recovery_invoked` and `inventory_recovery_status` in private Technical JSON. The query's returned inventory is only a candidate source; a label-filtered or even broad inventory record alone never verifies a device command, current router policy, delayed deadline or eventual effect.
- Preserve natural model reasoning: do **not** map model words to controller IDs, rewrite a command, automatically select a device, invent a missing driver command, create a Rule Machine rule or insert a general blocking scheduler.

## Synthetic regressions

Fictional media device with capability `NetworkDevice` has no network-policy command. A separate synthetic managed switch does and shares a source-reported physical reference. Test the sequence: narrow name match -> media details -> first model refusal -> a single unfiltered client source read -> independent model detail of alternate controller -> one `blockInMinutes` native call -> original alpha.65 read-only action/outcome review of the stored two-minute timer. Also check no broadening for questions, explicit read-only instructions, an already attempted native command, an already broad inventory, unavailable tools, exhausted time or repeat rounds, and safe reporting on a failed inventory read.

These are **scripted tool-selection** tests; they show the mechanism and permission boundary, not that the installed cloud model will necessarily discover the correct actuator or that a real router applied a policy.

## Acceptance

Require exact PR-head v2 pilot, release assurance and full repository validation, then merged-commit workflows. After installing alpha.73, make one separately authorized native delayed-block request and assess the *original successful and failed MCP receipts*: Did the model inspect the correct actuator instead of only the media record? Does the command match the requested delay? Was a native `blockInMinutes` receipt accepted? Is the pending state verified from native readback? Is later actual blocking observed? No source-independent router assertion.

**V1, Hub & Device Monitor, Cudy native command semantics, Rule Machine and other add-on paths are unchanged.**
