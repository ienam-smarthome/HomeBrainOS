# HomeBrainOS v2 alpha.75 — one-shot native timer versus unrequested automation

**Date:** 13 November 2026. **Baseline:** alpha.74 (restored alpha.65 native delayed-block action, alpha.73 inventory recovery, alpha.74 one follow-through). **Installed acceptance:** pending. **Live device changes from this code update:** none.

## Original live evidence and failure

An installed alpha.74 direct one-off request, “Block Google TV after 2 mins”, ended after discovering the separate native internet-management actuator in an unfiltered device inventory. It offered immediate device-off versus a temporary Visual Rule, incorrectly claiming no native delay command despite historical successful native timed-block receipts and a driver-supported delayed-block command.

A later user message “yes” followed that ambiguous either/or offer. The model made a hub backup, attempted unavailable hub_create_custom_rule (a local catalog error, not a hub execution), inspected the live tool catalog and Visual Rule reference, and created an initial Visual Rule. The first native response reported storedSuccessfully=true, activatedSuccessfully=false and validation errors: empty mode trigger and seconds=120 exceeding the seconds field maximum of 59. The model revised the rule to wait minutes=2 and a systemMode trigger set to the *current* mode Afternoon. This revision was stored and activated, but the rule now waits for a future mode-change event; it does NOT start a countdown now. An uploaded Hubitat screenshot confirms the wrong trigger. Its activation does not mean the requested one-off block was scheduled.

Independent earlier logs from the managed device showed a two-minute block scheduled at 11:55:37 and enforced at 11:57:37, followed by an allow event at 12:03:37. Those logs verify previous native device-timer behavior but do not prove either later HomeBrain request caused it.

## Scope of alpha.75

1. **Use native device timing whenever source-supported.** The existing alpha.65 native call path is preserved. A one-off relative action starting now is NOT a recurring automation with a mode, motion or other event trigger.
2. **Generic user-intent rule preflight.** Native rule creation/editing writer calls and gateway-selected equivalents are rejected before approval/native dispatch when the original user wanted only an ordinary one-off delayed device action, not a separate event-triggered/recurring rule. The original user request is retained across a bare yes/proceed follow-up; a model-proposed rule cannot invent authorization for an unrelated trigger. Actual explicit rule requests and event-driven automation requests remain permitted through all normal upstream backup and confirmation safeguards. The check never selects a device, native command or action.
3. **Continue after broad inventory even without details.** A successful alpha.73/74 broad inventory read containing candidate alternate control surfaces now qualifies for one model-led follow-through even when the model has not retrieved a detail read after the broad inventory. The model must still verify the physical actuator and advertised command itself; it cannot write automatically from an inventory list.
4. **Source-grounded rule reporting.** Original MCP rule response fields for stored status, activated status and validation errors are surfaced in private Technical JSON. A stored inactive draft is not an activated rule, and an activated rule is not proof a trigger fired.
5. **No hidden reversal of blocked state.** A device already in the requested final state with no pending timer is different from a new future transition. Do not unblock/allow simply to manufacture a delayed block without explicit authorization.

The repair is generic: it does not include device labels, real IDs, a Cudy-specific route, a new scheduler or a rule-machine workaround. Delayed **unblock** remains unimplemented. V1, external Hub & Device Monitor, the native internet-control driver, Rule Machine and the upstream MCP server are not changed.

## Synthetic tests and acceptance

Fictional tests cover a one-off delayed command being wrongly routed to a mode-change rule; the rule must be rejected locally before any approval callback or native writer. A fictional model can then use the already advertised native timer through the unchanged original MCP path. A bare yes to a multi-option suggestion cannot authorize a new trigger. An explicit real event-driven rule request remains allowed. The response parser distinguishes an inactive stored draft from activated rules. The broad-inventory checkpoint is tested without a later native detail receipt. No tests operate live devices.

**IMPORTANT:** The unintentionally created native rule (app ID 4299) is *not* paused, deleted or modified by this repository-only change. It was activated in the original receipt. The user must pause/delete it in Hubitat or explicitly arrange a connected hub write; pausing prevents new triggers but may not cancel a wait already started.

Release requires exact PR-head v2 pilot tests, release assurance and repository validation, followed by merged-head workflows. Installed cloud-model quality and real router enforcement require a new authorized live test with original MCP receipts.
