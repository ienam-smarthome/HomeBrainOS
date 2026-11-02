# Hubitat MCP AI v0.18.364 — read-only authority and evidence-preserving answers

## Real user regression

A user-requested **read-only** native Rule Machine inspection returned a false `request_class="write"` and the generic answer "I could not verify that this action actually ran", despite five successful read-only calls and no requested action. The trace showed **7 Ollama Cloud rounds, 5 MCP calls, 35.612 seconds**. The user did not ask for a mutation.

**Root cause:** The shared read-only authority parser interpreted the comma-separated negative list `Do not open native forms, create rules, submit confirmations or modify anything` as if `, create rules` granted independent permission. This set `_mutation_requested_by_user`; the final no-write-result guard then discarded the model's investigative answer.

## Correction

- Preserve the scope of an explicit `do not` across comma-separated action lists. A **new independent positive imperative** after a sentence boundary or `but/then` still retains normal write/confirmation requirements.
- Recognise negated `open` and `submit` in the shared negative-clause cleanup when a prompt does not contain an explicit `read-only` prefix.
- Add synthetic tests for the user-requested native-rule wording, other prohibited action lists, independent requested writes, unchanged scheduled-authoring authority, and the full request-publication boundary. No provider or live hub calls are needed.

## Native Rule Machine authoring status

Still **unsupported** on the newer native-document writer. The attached model answer reports a plausible existing Rule-5.1 time-trigger/Switch OFF sample (rule 4136), but its Technical JSON **does not include the `hub_set_rule(operation=read)` receipt the model claims**. Candidate parent 169 is inferred from counts, not proven child parent linkage; no dated one-time trigger or activation-after-once semantics are verified. See `docs/NATIVE-RULE-MACHINE-COMPILER-READINESS.md`. Do not fabricate or enable native creation from this incomplete source packet.

## Measurement and rollback

Expected after this change: the same prompt with five nonmutating reads should classify as a **live-read** and preserve the investigative model answer instead of the canned write refusal. Synthetic tests measure safety; real same-packet model-level improvement and wall-time are **NOT MEASURED**. Revert this release to roll back. No live Hubitat or Home Assistant changes were made during development.
