# HomeBrainOS 0.18.96 — One AI-interpreted investigation objective

## Motivation

The same original read-only Bedroom 3 Mesh MQTT/offline question was repeatedly reclassified downstream: keyword-triggered whole-hub audit, then historical ON/OFF command provenance, then prospective Rule Machine authoring because the request mentioned "automation behaviour" and "do not change anything". A succession of specialised keyword guards reduced individual failures but did not make the interpretation consistent.

## Architecture changes

- The bounded no-tools read router can now return a **structured, validated objective** alongside its workflow decision. It categorises the task as `device_connectivity`, `source_code`, `existing_rule_verification`, `rule_design_review`, `historical_command`, `general_investigation`, `system_audit` or `performance_report`, plus an optional bounded target label and concise purpose. The model may not infer actual Hubitat device identity or grant write permission.
- An immutable `ReadRouteDecision` is stored in a **request-scoped ContextVar**, and the original question is checked before use. The MCP tool loop, connectivity-depth tests, Rule Machine proposal classifier, existing-rule verifier, primary source/rule/device objective resolver, evidence-contract planner and final model synthesis all consume this shared interpretation rather than independently promoting incidental phrases into a new domain.
- A request can still contain implementation source, performance and automation references as supporting evidence without changing its primary investigative goal. `device_connectivity` is not historical command provenance; `rule_design_review` requires the affirmative model-interpreted task, not only a no-write qualifier.
- The validated intent is carried in the private `AgentOutcome` through `ObservedAgentOutcome` so the API's later evidence reconciliation receives **the same** objective even though the tool-loop context has ended. It is restored temporarily for final coverage and reset immediately afterward. No cross-request sharing.
- The host's **write intent detection is explicitly isolated from the AI objective**. A model classification cannot make an imperative command safe. Existing identity checks, command confirmation, tool allowlists, evidence receipts and write reconciliation remain the authority.
- Model replies with malformed JSON, unknown objective fields, missing data or unsafe report scope fall back to the existing bounded read-only investigation and legacy safety enforcement. Explicit whole-hub report commands continue without a model round.
- The extra no-tools interpretation round is used for ambiguous read workflows and recognisably analytical/deep read requests; trivial status lookups and actual write commands retain established fast/safety paths. The user's selected free versus paid model tier is unchanged.

## Verification

New tests replay offline/MQTT plus automation wording, source vs installed app IDs, affirmative rule design vs diagnostic reads, independent write detection, single model call/no tools, invalid model objective, cross-request isolation, evidence and output-stage continuity. All existing regression tests remain in the release gate.

## Limits

This consolidates the **task interpretation** used in the major read-only pipelines, but does not remove every legacy shortcut or alter the model's native tool planning. A correctly interpreted question can still end with incomplete source coverage or an uncertain root cause. A model can itself misinterpret a task; its output is a bounded advisory routing signal, not verified device evidence, authority to modify anything or proof that the user intended an inferred target identity.

No live Hubitat settings, rules, drivers, devices, or model billing settings are changed by this release.
