# HomeBrainOS v0.18.44 — Route configuration-focused hub audits deterministically

## Live observation driving this release
A genuine v0.18.43 Free Gemma whole-hub read-only request concerning scheduled jobs, disabled automations, heartbeat and overlapping lighting rules returned via `unified-mcp-agent`, with 11 model rounds and 87.9 seconds elapsed. It read one unrelated app config and never produced the new `chat_audit_app_dependency_configuration` receipts. That result does not establish a fault in the configuration probe; it exposes a routing gap.

## Changes
- Recognise a **whole-hub configuration dependency audit** when the prompt requests an actual multi-domain scheduler + automation + device-target investigation, even when it does not literally say "logs". Keep targeted device-cause, scheduler-only and performance-only questions out of that route.
- Prevent the automation-status shortcut from intercepting the newly recognised cross-domain request; send it to the existing deterministic `run_comprehensive_chat_audit` path, which invokes the v0.18.43 bounded read-only configuration probe. Optional tool-free synthesis remains opt-in and the default requires no model round.
- Independently compare typed device IDs retrieved from structured action-scoped fields, even where the MCP config does not include readable action paragraph text. A typed shared target is **configuration evidence only**, never proof of callback execution or a real conflict.
- Tests include the **exact failed live prompt**, route dispatch without a model, scheduler-only and single-device negative boundaries, typed action-only overlap, trigger-device-only negative cases, and wrong-app ID protection.

## Limitations and next live verification
The new route must be re-tested after installing v0.18.44. It should render "Automation configuration and dependency investigation" and generate `chat_audit_app_dependency_configuration` receipts when qualifying installed app IDs and app configs are available. Missing scheduler job owner fields still prohibit claiming disabled-app execution. This release does not mutate automations, devices or settings, and makes no upstream MCP server changes.

Merge only after all three CI workflows pass.
