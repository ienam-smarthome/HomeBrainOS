# v0.18.33 — Stop explanatory investigations being classified as writes; correct Free-model billing metadata

## Live v0.18.32 evidence (18 October 2026)
Three independently uploaded HomeBrain responses:
- Two deterministic read-only comprehensive audits showed **207 detailed MCP-visible devices, 152 normalized automations, 3 explicitly offline devices and 0 low-battery reports**, with 200/200 log sample saturation. The alert count changed **5 → 4** as sampled warnings and an MCP Rule Server log timeout differed between runs. These are distinct audit snapshots, not a verified disappearance of any permanent issue.
- The Free Gemma investigation used **eight model rounds, seven tool calls, 46.9 seconds**, and retrieved targeted Bedroom 3 Mesh state/history (including a truncated current `deviceHealth` page). Despite making **only read tool calls**, it reported `request_class="write"`, returned a generic "I could not verify that this action actually ran on Hubitat" write refusal, and reported `success=true/outcome=success` while counting `task_evidence_incomplete=1`.
- The same Free response incorrectly labelled eight `gemma4:31b` rounds as billed under `anthropic-account`, despite `paid_rounds=0` and `model_tier_requested=free`.

## Root cause
The broad mutation parser interpreted the literal explanatory terms `switch=off` and `command-off` as a request to switch something off. The narrower `_explicit_mutation_request` had an exception for "Verify whether", "Why" and some causal prompts, but not standalone analytical questions starting "Explain", "Compare", "Distinguish" or "Describe" unless they contained a `why` clause. The result misclassified an evidence-only question as an authorized user write, and the mutation-verification guard replaced a useful evidence-limited answer with a refusal.

In a second pathway the agent marked mutation state when merely *proposing* a mutating tool, before it was actually authorized or dispatched. This could also incorrectly mark a read-only question as a write.

## Changes
- The intent boundary now recognizes explanatory/investigative lead-ins as read-only, while still routing mixed later explicit writes ("Explain ... Then turn off ...") into the existing guarded confirmation path.
- A model-selected state-changing proposal during a read-only request is atomically refused **before** mutation state is marked or any call is executed. No other tool in that proposal round is executed, and a diagnostic `read_only_model_write_blocked` counter records it.
- An incomplete evidence task (`task_evidence_incomplete`) maps to `outcome=unresolved` rather than the success default, with hard failures still taking precedence.
- Free-only Ollama model rounds report `charges_controlled_by=ollama-free-allowance` rather than Anthropic billing. Paid Claude/DeepSeek billing classification is unchanged.

## Clarifications
This release addresses request semantics, outcome/billing metadata and safety. The Free response did **not** make the exact historical app 3950 ON/OFF investigation: it read an unfiltered newest-first device history page saturated with watchdog `deviceHealth` events and only current diagnostic logs. Therefore that result does not yet test whether the v0.18.32 mandatory `command-off` reader works for the original fully specified question. The audit requests likewise are comprehensive health checks, not this historical command-regression test. Exact user prompt text is not embedded in these responses, so this diagnosis is grounded in the observed classification and the earlier provided test wording, not claimed access to a missing original prompt field.

## Tests and next validation
Regression tests cover the prior "Explain the difference between switch=off and command-off" prompt, mixed explicit writes, live-read classification with read receipts, incomplete outcome mapping, registered read-only proposal-block telemetry, and Free Gemma billing.

CI must pass all three required workflows. After installing, repeat the explanation using Free and confirm `request_class=live-read`, `outcome=unresolved` if verification is incomplete, and no anthropic billing metadata. For the historical-command regression, run the *fully specified* app 3950/device 7103/12 October ~01:30 read-only question; expect an attempted `hub_list_device_events(attribute=command-off)`. Do not infer a command issuer from a state event. No Hubitat changes.
