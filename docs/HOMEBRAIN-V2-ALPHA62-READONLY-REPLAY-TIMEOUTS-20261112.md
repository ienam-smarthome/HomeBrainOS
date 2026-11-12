# HomeBrainOS V2 alpha.62 — Preserve failed native read-only MCP attempts in frozen evaluation

**Date:** 12 November 2026. **Scope:** Optional AI Evaluation replay and offline frozen-receipt evaluator only.

## General failure mode

An agent may initially attempt a large read-only native MCP inventory/history/configuration request and receive an **MCP timeout**. The exception path produces a `success: false` receipt without `operation_executed` or `read_only` fields. The agent can then retry with a smaller read query and return a valid first answer. This is distinct from an uncertain failed **write-capable** operation.

Alpha.61 rejected such a frozen bundle with `Uncertain failed operations cannot be replayed as read-only`, despite the native read-only tool contract. The conservative execution-metadata rule was appropriate for mixed-action tools, but "unknown whether a READ executed" is not a device-write risk when the native tool is *by contract read-only*. A timeout does **not** prove the read succeeded.

## Corrected replay acceptance

The phone evaluator `rootfs/app/frozen_evaluation.py` and offline `evaluation/frozen_model_replay.py` accept original failed receipts with no execution flag **only** when the recorded tool belongs to the established, informational native MCP families `hub_get_*`, `hub_list_*`, `hub_read_*` or `hub_search_*`, and does not explicitly contradict read-only status.

Existing protection remains: unexpected tool names, mixed-action `hub_manage_*` operations, explicit `read_only:false` failures lacking independent proof of non-execution, prohibited tools, no successful receipts, and attempted new model tool calls still fail. Previously accepted argument-validation failures for the reserved local Hub & Device Monitor helper remain supported.

The original failed read, its error and timing remain in the serialized frozen source and **are counted as failures**, never as successful reads. The replay makes **no MCP calls or writes**. It does not silently truncate, hide the timeout or infer completeness from later summary queries. It does not add automatic AI adjudication or host-written answer patches.

These rules reflect the existing installed upstream Hubitat MCP read-only tool contract, already used in `investigation_review.is_read_only_review_tool`. The generic predicate is about a **tool class**, not a particular device, name, incident or error message.

## Related model-quality finding

An unrelated first-answer quality issue was exposed by the read-only inventory test: a generic Hubitat device `lastActivity` timestamp is **not necessarily** the timestamp of the latest `battery` attribute reading, and a stale last-activity date does **not** independently prove that a device is offline. Likewise, an inventory listing of devices with missing `battery` attributes cannot prove those devices are battery-powered. These are cross-domain provenance principles for evaluation, not new prompt restrictions in alpha.62.

In that test, the initial full detailed inventory query timed out, and the successful smaller summary inventory returned three below-threshold battery values. No status-verification source was retrieved. The new replay fix allows unbiased comparison of the full original **failure plus success** set, rather than excluding the timeout, without changing the quality of the initial answer.

## Acceptance

Synthetic tests exercise a read-only native timeout, preservation of original failure, rejection of `hub_manage_*` names and explicit read-only contradiction, and no-model-tools replay; both replay implementations are covered. Run all V2 pilot, release assurance, repository validation, full Python and add-on container checks prior to merge.

Normal Ask reasoning, model prompts, MCP tool operation, write permissions, Hub & Device Monitor, V1 and all hub/device configurations remain unchanged. Real private source rows, identity data, network addresses, receipts and model answers are not committed.

**After installation**, the user can import the existing private Technical JSON directly to AI Evaluation or run a new Ask. Each model replay still requires explicit one-time consent when the configured model is cloud-hosted. Human scoring remains required; a completed frozen replay is not proof of factual correctness.
