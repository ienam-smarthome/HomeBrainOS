# HomeBrainOS v2 alpha.67 — model-led discovery of the actual control surface

**Date:** 12 November 2026. **Scope:** V2 normal Ask tool/source selection, only. **Installed model-led first-answer acceptance:** pending. No real hub/tool writes or household identifiers embedded in the implementation or fictional fixtures.

## Source-real motivation

Two private alpha.66 first answers failed requests concerning a named media endpoint and a timed access-control action:

- A read-only comparison correctly distinguished delayed start from immediate temporary allowance, but a narrow `hub_list_devices(labelFilter=...)` returned only media integrations and an unrelated virtual helper. The model inspected two media devices, assumed that their lack of internet-blocking commands meant the action was impossible, and proposed an unnecessary automation.
- A direct delayed-unblock request inspected one speaker/media record, saw no network-access command, and declared that the named target could not be unblocked at all. No alternate control surface was searched. Both requests completed without tool errors or writes.

The narrow list operations were successful **but not capability-complete**: a device's media/power/network status integration is not necessarily the device or rule that controls the requested physical effect. Another controller may be inventoried under a different label or prefix, and the list's `unfilteredTotal` can disclose a much larger candidate set.

This is a **general device identity vs action actuator vs timing** source-completeness failure, not a reason for new internet-blocking semantics, a special media alias, a new scheduler or a per-device patch.

## Implementation

1. Strengthen initial model guidance to identify the user's physical target **separately** from the requested effect and the actual native controller of that effect. One physical entity can have multiple installed integrations exposing different commands. Neither shared labels nor coincident network identifiers are sufficient proof of physical identity; require corroborating source evidence before writes, and ask if ambiguous.
2. Explicitly state that a successful narrowly filtered inventory (including a `labelFilter` with small `count` relative to `unfilteredTotal`) is not an exhaustive search of all alternative actuators. Model may choose broader `hub_list_devices` (including the server-advertised `format=context` if available), relevant native detail reads, rule/automation reads or earlier source evidence. No hardwired tool order, query substitution, or native read is executed automatically.
3. When the model completes an answer that **denies a capability**, the existing optional evidence-sufficiency loop may offer **one read-only, model-selected control-surface discovery review**, if actual read tools and deadline headroom exist. The trigger looks only at generic *drafted denial language*, not domain/device names, control keywords in the user query, or incident-specific IDs. It does not rewrite the answer or automatically choose a controller. If further sources matter the model selects them. If still unresolved, scope any negative finding to the checked records.
4. The review excludes native writes, even when the user originally requested a write; the agent can only investigate and answer at this stage. It cannot fix, retry, run a different action, create a rule or silently change the device. The existing additional text-only final audit is skipped for this targeted review to avoid extra latency and certainty amplification.
5. The private Technical JSON records `source_review_kind=capability_discovery` and preserves original read receipts and the pre-review draft. No change to the MCP server, prior V1, Hub & Device Monitor, confirmation, authorisation or error semantics.

## Synthetic regression coverage

A fictional display endpoint and separately named actuator share an explicitly returned physical reference. A scripted model initially declares an operation unsupported after a narrow label-filtered inventory, then chooses a broader inventory and the alternative actuator's detail read *during the read-only checkpoint*. The test asserts **zero write calls** and no automatic selection by the agent.

Additional tests: broader inventory has no matching actuator and the answer retains source-bounded uncertainty; positive read-only reply does not incur additional review; model request for a write during the review is refused; and the generic denial trigger is independently exercised without any literal household labels.

These tests prove that the review is accessible and safe under model-selected tools. They do **not** prove a particular installed LLM will proactively search all relevant actuators, correctly match two records to one physical device, find an unindexed controller, or choose an authorised write first time.

## Deployment/acceptance

Require exact PR-head pilot, validation and release-assurance CI, then merge and post-merge checks. Install alpha.67 for a new source-real read-only question where a named endpoint's listed device cannot perform a requested function but another integration might. Review original tool receipts: did the model broaden the scope, retrieve any alternative controller, verify target identity and timing semantics, and avoid unsupported global negatives or unapproved writes?

A live state-changing test should remain a separate explicitly authorised operation, especially for household internet access, power and safety systems. The addition is general agent reasoning and a model-led read-only checkpoint, **not** a deterministic device-name router.
