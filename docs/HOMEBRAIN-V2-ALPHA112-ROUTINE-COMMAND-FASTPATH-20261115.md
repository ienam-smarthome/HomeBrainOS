# HomeBrainOS V2 alpha.112 — source-verified routine-action fast path

**15 November 2026. V2 Preview only.** No private household information, IP addresses, genuine target IDs, prompts or original native source receipts in this public development record.

## Why this milestone

Owner-reported early native controls previously felt about 5 seconds. Installed alpha.110 simple ON/OFF first attempt stopped with text-only No action queued; a separately selected retry obtained an original native command acceptance but took ~21.4 s, **six model rounds** and ~290k provider-reported input tokens, with ~2.25 s actual human approval wait. The preceding alpha.111 corrects an internal UI retry instruction being concatenated into a user imperative and the resulting incorrect lifecycle classification. Alpha.111 does **not** remove the optional pre-dispatch reflection and source-review model turns.

The full V2 agent deliberately contains general safety/evidence work for multi-device effects, network control, delayed schedules, native rules and contested causal questions. The small source-verified ordinary device control subset need not incur every optional review after the correct live device and command are already established. Never conflate initial response time, model time, MCP time and user approval wait. No proof of a 5-second result exists for this implementation.

## Implementation boundary

New `routine_action_fastpath.py` is a **validator/projection only**, not a command router. The connected model still chooses original, advertised native tools and arguments. The fast-path may qualify only when all these conditions hold:

- The user's *original* request is a single direct `turn/switch on/off [exact label]` imperative. It contains no inferred physical effect, timing, conditional clause, multi-step operation or compound action.
- Exactly **one** model-selected `hub_call_device_command` proposal targets that literal label and matching `on/off` verb, with no extra arguments, alternate device, helper, schedule or proxy.
- Current-request ORIGINAL successful `hub_get_device` details agree on requested/returned ID, exact label, `Switch` capability, advertised no-argument `on/off` command and current reported opposite switch state. A label-only filtered inventory, stale previous chat, failed/extra detail or unrelated source is not enough.
- Existing same-request source and native approval checks are NOT skipped or modified. There is no direct client/tool dispatch from the request string.
- Before native dispatch, this narrowly verified proposal may skip **only** the redundant prewrite model reconsideration. After the existing approval gate and real native transport return a matching, explicit **successful original acceptance**, the terminal response may use a short source-derived acknowledgement without a further model review. An embedded state snapshot is NOT independent readback. Rejection/unknown/error keeps the normal model-based workflow. Approval decline never produces a fabricated accepted result.

For all other classes (timers, rules, delayed/conditional or compound actions, claimed network-policy effects, unverified target identity or state, missing native capabilities, multiple tool calls, failed sources), the current model-led V2 safeguards remain enabled.

## Acceptance and measured cost

Synthetic regression fixtures use fictional local MCP responses and scripted AI rounds with an actual `Interaction(require_native_write_approval=True)` pending gate. They require the correct source-first native writes to be blocked before approval, run exactly three model rounds for search + details + selected writer (instead of a redundant prewrite and post-write round), preserve original accepted receipt and `action_lifecycle=native_accepted`, and forbid physical-outcome claims. Negative tests cover incorrect IDs/labels, already-satisfied state, missing capability/command, altered arguments, multiple writes, unverified/failed original receipts, network-policy or scheduled requests and old/missing sources. These tests do not prove inference quality or production speed.

**Installed independent acceptance remains required.** Capture one uncoached new benign ON/OFF device request, exact original successful MCP receipts, approval timing, model rounds, prewrite and post-review flags, any tool errors and independent post-write state if needed. If model stalls in prose or goes through complex/tool-heavy planning, the fast path intentionally cannot force an operation. Never patch a particular device or remove approval to improve a benchmark.

## Rollback

If it skips a necessary review for a wrong target/effect or reports success unsupported by the original native receipt, revert alpha.112 routine shortcut; keep alpha.111 request-intent correction. V1 untouched.
