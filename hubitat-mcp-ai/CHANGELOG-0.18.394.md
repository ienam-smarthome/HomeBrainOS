# HomeBrainOS 0.18.394 — native dated Rule Machine Switch writer

## User-observed baseline and causal hypothesis

Direct Google TV Internet Switch `off()` succeeded on device 6923 in ~2 seconds. Requests to schedule the identical control action after X minutes or at a specified Hubitat-local time were blocked by a correct but outdated HomeBrain legacy `addTrigger/addAction` writer. Upstream [MCP Rule Server issue #575](https://github.com/kingpanther13/Hubitat-local-MCP-server/issues/575) fixed native `date` input validation in server v5.1.6. A separate v0.18.392 0.7s answer incorrectly listed 165 automations for a single named rule; v0.18.393 independently fixed named-rule read routing.

## Scope and contract

This release admits only source-attested **one-time, single-action, typed native Switch** rules through the existing sensitive-operation confirmation boundary. A request like "block Google TV Internet after 15 minutes" or "block Google TV Internet at 8:00 AM" becomes a future **dated Certain Time** native trigger with one OFF Switch action. A daily recurring request, multi-action automatic restore, rule edit, untrusted action subtype, unverified parent or non-5.1.6 server still fails closed. The only source-verified Internet meaning here is that `off()` blocks and `on()` allows. Other switch commands receive their literal effect.

The compiler checks local hub timezone and future time (including DST), resolves device identity/command, uses exact native `time#`, `atTime#`, `date#`, `atDate#` fields, and rechecks duplicate names, version, typed parent and document integrity on approval replay. Both source reads and proposed writes have distinct evidence; no actual device command occurs when scheduling. Upstream write may leave a partially configured rule after an error; HomeBrain will **not silently retry**. It reports the source rule ID, explicit partial/unknown outcome, and recommends inspecting/removing the incomplete rule manually. For a confirmed creation, require persisted matching rule document, nonbroken native status and activation jobs/subscriptions; this does not prove future triggering or Internet availability.

## Testing, risk and rollback

No live Hubitat, HA or router actions were performed by this PR. Synthetic tests cover issue #575 field contract; installed version identity (>=5.1.6), parent identity, duplicate rejection, strict proposal schema, explicit confirmation, native receipt verification, no optimistic partial success and existing legacy regressions. Full repo CI results are in the PR. Real v0.18.394 first-run scheduling success, measured scheduling latency, trigger execution, physical Internet effect and model quality remain **NOT MEASURED** until an operator supplies safe read-only follow-up after an authorised tiny test rule.

Rollback: revert this release if native scheduling produces unverified/incomplete children; keep direct commands available. Never execute or modify a live Rule Machine rule from a GitHub PR.
