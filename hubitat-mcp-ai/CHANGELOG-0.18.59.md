# HomeBrainOS v0.18.59 — Read-only Rule Machine proposal boundary

## Live regression
On 2026-10-22 the user compared a proposal-only Rule Machine benchmark with Claude. HomeBrain v0.18.58 returned `request_class="write"` and the generic `UNVERIFIED_MUTATION_REFUSAL` despite ten successful **read-only** tools, 26.6 seconds elapsed and no write/confirmation. It misinterpreted "I want to create ... but review existing automations, propose implementation before making changes; do not create, modify, disable, execute or queue a write yet."

The benchmark also included a mismatched sensor ID: device 7764 was reported by Claude as **FP300 Toilet sensor**, not Livingroom. App 4019 already issues actual OFF commands to Light 7805. HomeBrain retrieved app-labelled command history and lockout reads but produced no useful plan or mismatch verification.

## Fix
- Add high-precision `RuleAuthoringService.is_read_only_rule_design_request` for explicit proposal/review with separate no-write/no-queue instruction. Do not treat future desired-state language as present mutation authority; reject independent immediate write commands.
- Route these requests through the existing read-only `review_first` permission gate: never expose modifying MCP gateway, do not create/queue a pending action, preserve source receipts and classify as `live-read`.
- Make the final reply a read-only **rule design** review, retaining actual findings rather than replacing it with a bogus failed-execution refusal. Block unsupported "I created the rule" claims.
- Give the model a dedicated evidence-first plan: verify the claimed ID's actual label/room/capabilities, read exact existing app configuration and dependent apps, compare 4019's currently configured OFF logic, distinguish action-level evidence from historical commands, state whether native RM operations are actually documented, and explain a correct overnight/cancellation design.
- Do not hijack proposal-only tasks into the separate manual lockout historical fast path simply because they mention that lockout.
- Leave ordinary authorised create/modify/disable requests and separate confirmation pipeline unchanged.

## Safety and limitations
The new classifier does not author, simulate, validate or create a complex Rule Machine rule. The existing `RuleAuthoringService` deterministically compiles only a limited set of simple scheduled rules; the model must admit unsupported multi-trigger wait/cancel semantics rather than invent `hub_set_rule` payloads. Even documented native action availability does not prove the exact combined behaviour. Source reads may have native Hubitat rendering side effects, although this change performs no write command.

Regressions include the complete live benchmark, explicit conflict/independent-write negatives, no confirmation/no write, retaining successful read evidence and guarding false write claims. All three CI workflows required before merge; live add-on retest required.
