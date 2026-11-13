# HomeBrainOS v2 alpha.77 — Model-led pre-dispatch evidence reconsideration

**Date:** 13 November 2026. **Purpose:** General action-quality improvement, not an incident-specific routing patch. No real Hubitat device, router rule or automation is changed in this PR.

## Evidence-led diagnosis

Two private source-real action captures exposed a failure of source-to-action alignment. A label-filtered device inventory returned an integration with a similarly named target. Its native commands controlled one facet of that device, not the requested downstream effect, yet the model attempted an incorrect action and then built a persistent event rule as a workaround. In a second session it tried native rule writers using older prior receipts without a fresh domain read, stored inactive drafts before successfully storing an active rule, and later inferred a pending countdown from the trigger switch state without source evidence of the rule's internal wait execution.

The underlying problems are **generic**: matched labels do not establish physical effect, separate endpoints can control different facets of one system, delayed onset is not the same as a recurring event trigger, stored drafts are durable artifacts, and an after-action source review cannot undo an unnecessary write.

**Do not publish original private MCP source receipts, physical device IDs, household names, or credentials in public repository history.** The test fixtures are fictional.

## Narrow architecture change

1. On the **first model-proposed mutating native call in a live UI request**, defer all proposed calls before any native submission. Give the SAME connected model **one bounded source-alignment reconsideration**: actual user goal's target, desired effect, timing, current successful domain reads and the selected but UNEXECUTED tool/arguments. The model chooses its next native read or action (or a genuine blocker). The client does not map devices, select a new action, inspect a physical router, create automation or run a scheduled callback.
2. A proposed tool call that is reconsidered is **not** an MCP receipt and is not appended to conversation history as an executed tool. Separate Technical JSON telemetry reports whether the reconsideration ran. This is limited to one review, and normal answer/contract safety checks stay in place.
3. After such reconsideration, **persistent automation/helper creation** requires at least one successful CURRENT-request native domain read. Tool guides, schema inspection, prior conversation and failed reads are not current state. On failure, the write is rejected before the native MCP server and before human approval; its local receipt identifies nonexecution. The model chooses further evidence without a hardcoded tool sequence. Identity/effect suitability beyond that minimum remains a MODEL judgement and a remaining live-test risk.
4. Keep the alpha.76 independent approval for actual persistent native rule writers, native server permission/backup preflight, and original state-versus-command/outcome distinction. Ordinary native device-owned one-shot timers retain their commands and are not blocked by the persistent-construction evidence floor.
5. If the native rule writer returns `storedSuccessfully=true`, `activatedSuccessfully=false`, it has created an **inactive durable draft**. Model instructions prefer reading/updating that same app through its source-supported revision contract rather than creating additional same-named drafts. Do not retry an uncertain write blindly.

## Meaning of “one-off” and alternatives

A one-off delay requested **now** is one future transition, not a recurring event subscription. A native device-owned timer is often simplest if the real target independently advertises a matching delayed command. A truly one-time rule is also an acceptable model-chosen implementation, but only if the **current native MCP/hub contract** supports its trigger, precise firing time, target action, and one-shot lifecycle. A persistent Visual Rule such as `switch turns on -> wait 2 minutes -> turnOff` is **not inherently one-off**; it can execute again on a later switch-on and its stored/activated status does not establish that the wait started or the target was affected. Do not invent an absolute-date Rule Machine contract when the native server has not exposed one.

## Acceptance

Fictional, isolated tests cover the wrong-facet media-interface proposal being **dropped before dispatch**, independently chosen broad inventory and a native deferred command with readback, a persistent rule proposal from prior-only evidence being **rejected**, and a legitimate event rule proceeding after a fresh read and ordinary approval. These are *scripted test flows*, not evidence that `gemma4:31b-cloud` will choose the right tools on an installed request.

For installed acceptance: ask a fresh, ordinary one-off action without telling the model what command, driver, tool, rule or ID to use. Inspect the first answer and original PRIVATE Technical JSON; establish whether its selected actor can deliver the requested physical effect, verify the native pending deadline if a device timer is selected, distinguish rule storage/activation from trigger execution if a rule is selected, and independently check later physical effect only when actual source data permits. Do not create test rules from this repository audit. After measured success, resume Gate B's cross-domain first-answer evaluation. V1, existing external diagnostics, Hub & Device Monitor and router/controller code remain unchanged.

## Limits

The checkpoint is an added model round, not a proof of correctness or a deterministic semantic planner. It may increase latency. An incorrectly selected actuator can still be chosen after review; normal permissions and user judgment remain necessary. The fresh-source floor establishes *some* current native reading, not a perfect device-effect mapping. The change is an evidence-based model-led experiment to evaluate against new live first answers, not a claim of solved general reasoning.
