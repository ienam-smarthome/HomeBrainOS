# v0.18.268 — V3 evidence-ranked, model-selectable upstream read frontier

## Problem demonstrated by 0.18.265/0.18.267
The original agent can recover source-qualified switch states and discover a sensor whose ten collector receptions uniquely pair with five light cycles. However, its generic read feasibility planner enumerated unchecked target dependents and app configs without promoting the *strongest observed input sensor* into a dependency read. Spending more model rounds on unrelated sensor logs could never establish the missing initiating controller.

## Design
- Add `causal_upstream_read_frontier.py`, a pure bounded source projection over already recorded current-request read-only receipts.
- The candidate input must have a source-qualified target receiver pattern, at least three ON and OFF pairings, a full untruncated input journal page retained in the receipt, a successful independently scoped native device history, and a successful scoped journal input recovery. No room-name matching or hard-coded sensor IDs.
- Suggest `hub_list_device_dependents(deviceId=<verified input>)` only when that exact input has not already been attempted and the same READ leaf already succeeded in this request. It is model-selectable, never host-executed.
- If both the input and a target have successful dependency reads carrying explicit structured `appsUsing` IDs, suggest `hub_get_app_config(appId=<intersection>)` when its READ leaf is known usable and the shared app has not already been attempted. A textual summary naming appsUsing is insufficient to establish app IDs.
- Suggestions are ranked ahead of generic target dependency and command-app config reads, deduplicated by exact leaf and args, and included in the recovered-journal model checkpoint.
- An attempted but failed input dependents/config read is marked as attempted rather than silently retried. No phantom leaf, new permissions or extra model round is introduced.

## Safety and acceptance
- All timing is collector-reception evidence, not original input event time; current app association is not past app execution or historical command issuance.
- The natural-language finalizer, existing digest fallback, typed-witness validator, and device/automation mutations remain unchanged. A later separately reviewed model-publication stage is required to safely retain native prose.
- Regression fixtures rename devices/IDs and test priority, shared-app escalation, prior attempts, unadvertised read leaves, incomplete archives, missing target source/collector pairing, and maliciously invented lead IDs.
- After CI succeeds, replay the *same read-only* Bathroom incident and inspect whether the model chose the top ranked `hub_list_device_dependents` for the strongest input within its existing budget, then whether a shared app config was actually available. Compare rounds and tool calls; do not equate any app association to the incident root cause.
