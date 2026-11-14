# HomeBrainOS V2 alpha.94 — contradiction-aware source review and concise final audit

**Date:** 14 November 2026. **Scope:** V2 Preview only. The original model-led and native approval architecture stays intact.

## Motivation and external validation scope

A source-real V2 alpha.92 first-answer investigation reported a genuine OFF observation, a previous ON, correlated environmental readings, a relevant controller configuration, but no corresponding device command. The model favoured an internal controller timing path despite a current configuration page showing its relevant capability input as **explicitly unselected**. It also attempted to read the controller's own event history but received **MCP HTTP 503**; its final prose obscured that failure. The last model round was much longer than earlier inference rounds and repeated lengthy tables.

Those are **general classes** of incomplete evidence handling, not proof the model was incorrect about any underlying real-world event. Neither a missing command nor current unselected capability input proves an action never occurred.

## Changes

1. **Source-derived null/empty config scope:** `config_source_map` now retains a bounded list of capability inputs with an explicit `value: null` or `value: []` on the *returned current app page*. Previously only selected/non-empty inputs were highlighted. An input with no `value` field remains unknown, not unselected; sensitive field names and long UI content are excluded. The map is NOT an execution trace, historic configuration or complete installed-app settings inventory.
2. **Already-available receipt navigation:** The existing, bounded `final_claim_receipt_scope_index` adds the source map's explicit empty-capability input observations and classifies failed tool receipts by safe generic code (e.g. `http_status: 503`) rather than copying private raw error messages. A failed call is *not* a successful empty query and cannot establish absent action. The index still contains no copied raw log payloads, credentials or full device records.
3. **Model-led contradiction handling:** Source review and final audit now explicitly examine contradictions between observed event timing, selected/unselected configuration inputs and the proposed internal controller path. Current configuration might have changed, the actual rule may use other linked pages, and another controller could operate the device—none is assumed true without source evidence.
4. **Preserve source failure in final prose:** A relevant failed read must be identified by tool and unavailable status, and not silently converted to "no logs found" or a source with no events. No automatic retry or new tool is introduced.
5. **Concision instead of additional model rounds:** Existing final tool-free audit now targets about 350–550 words in routine causal investigations, unless user explicitly requests a comprehensive report. Preserve exact material chronology, scope, uncertainty and failures; avoid repeated historical tables and internal preparatory narration. This is prompt guidance, **not a hard output token cap or a guaranteed latency reduction**.

## Safety and unchanged contracts

- No forced tools, new compulsory model rounds, deterministic cause attribution, generic forced logging or event replay.
- No changes to V1, device command dispatch, authorisation/approval, or paid/free provider choice.
- No claim that current UI configuration proves event-specific execution or excludes hidden/earlier actions.
- No raw private source material added to the navigation summary, no credential copying.
- Prior source-real data may motivate generic tests, but the CI regressions use separate **fictional data**.

## CI and source-real acceptance

Run Python suite, metadata validation, add-on build and smoke tests. Synthetic tests check current explicit-null versus absent values, positive selected inputs, sensitive-name filtering, failing HTTP/unknown results, source immutability and audit output guidance. CI does not establish model compliance or live Hubitat causality.

After update to alpha.94, obtain a **new** source-real first-answer causal investigation. Compare original successful MCP receipts and source failures to the final answer: chronological evidence, source limits, positive command issuer, current config contradiction, unknown internal cause, failed read preservation, no writes, model round count, `eval_count`, `prompt_eval_count` and total duration. Keep the provider constant for an interpretable comparison.

### Performance hypothesis

The 350–550-word request may reduce redundant output and latency on models that follow it. Since model reasoning and tool-choice patterns vary, actual speed or token savings must be measured; avoid asserting improvement solely from the synthetic CI results.
