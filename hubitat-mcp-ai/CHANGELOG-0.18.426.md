# HomeBrainOS v0.18.426 — remove native Rule Machine inventory fast path

## Installed failure (5 November 2026, 21:42 UTC)

The installed v0.18.425 read-only MCP Rule Server v5.1.6 **dated-trigger runbook authoring-contract review** was incorrectly intercepted by a deterministic Rule Machine parent/name inventory response, despite v0.18.425's correction to the model-led `rule_design_review` objective. The output asserted Success and completed only parent identity / exact saved-name inventory, not the requested typed trigger, log-action, date/time/year settings, backup, or scheduler contract. Five tool receipts (four nonmutating MCP reads plus a local typed projection), ~4.6s wall, zero provider rounds; no Hubitat writes or confirmation.

This is a false-positive completion and wrong response to the request, **not** proof that the native dated-trigger contract is ready.

## Removal

- Delete the dedicated native Rule Machine parent/suffix inventory source module and its two now-obsolete specialised test suites.
- Remove the orchestrator's deterministic inventory early return and implicit first-matching native-document read. Remove its inventory-specific import, its exemption from the investigation-unfulfilled boundary, and its special evidence-plan bypass.
- Remove the shared completion branch that converted a typed parent/name inventory projection into a successful answer independent of the user's actual authoring-contract question.
- Replace obsolete tests with a regression that feeds former inventory-shaped evidence to a runbook review and requires that it **cannot** satisfy the intended authoring schema or mark the response successfully resolved.
- Do not route a native schema review into an existing installed-rule action-tree audit as an alternative.

## Preserved functionality

The underlying MCP read-only APIs (`hub_list_apps`, `hub_list_rules`, exact-ID native rule readers, native parent readiness, and bounded existing dated-trigger discovery) remain available independently. Ordinary rule listing continues through allowed reads and source-scoped analysis, rather than an answer-replacing special fast path. Dedicated unrelated device inventory and automation-status features remain unchanged.

No new Hubitat calls, rule/device writes, editor forms, model permissions, confirmations or native scheduling capabilities are introduced. `readinessForMutation=false` remains a requirement for any unverified native contract.

## Acceptance

After CI passes and 0.18.426 is installed, run one read-only authoring/runbook review identical to the failed 0.18.425 request.

Expected: no local parent/name-only completion, no inventory-only Success or irrelevant rule audit, with `investigation_coverage.domain=rule_design_review` and typed-authoring-contract requirement correctly unresolved unless a real source-attested typed schema exists. Measure wall time, model rounds and tool calls without inferring improvement from green CI.

Historical release notes are retained for audit but **do not represent currently installed code paths**.
