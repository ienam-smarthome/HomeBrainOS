# HomeBrainOS V2 alpha.60 — reject unsafe operations, not failed read-only probes

**Date:** 12 November 2026  
**Affected feature:** Optional phone/CLI frozen-receipt AI evaluation (alpha.59)  
**No changes:** normal Ask/Chat agent, MCP server/device commands, model prompts, review timing, V1 or the external recorder

## General failure mode

The alpha.59 in-browser AI Evaluation can reject a read-only source capture with "Uncertain failed operations cannot be replayed as read-only" even though every attempted tool is intrinsically read-only. Specifically, the local `homebrain_read_device_monitor` helper permits only `status` and `history`; invalid read arguments can raise before the agent populates `operation_executed`, `read_only` or `result_kind` on the failed receipt. A later valid read can succeed. This metadata omission is **not evidence that a write occurred**, and a failure is not evidence that the read succeeded.

Previously, the evaluator required every failed receipt to explicitly declare `operation_executed=false` or `result_kind=contract_error`. The broad requirement was appropriate for untrusted native/mixed-action operations but unnecessarily rejected the reserved, inherently read-only monitor helper.

## Implementation

Both the in-add-on frozen evaluator (`rootfs/app/frozen_evaluation.py`) and the optional offline model replay (`evaluation/frozen_model_replay.py`) now classify a failed attempt as accepted read-only evidence when its tool name is **exactly** `homebrain_read_device_monitor`, its arguments are a mapping, its mode is `status` or `history`, and the receipt does not explicitly contradict read-only status. All original failed receipt fields, including the error, are **retained** and counted as failed calls; none are promoted to successful reads or proof of historical coverage. This exception relies on the local tool's reserved, implemented read-only contract, not on text supplied by the model.

The strict existing checks remain for every other tool: unsafe names are rejected, and failed native `hub_get_*`/`hub_read_*` attempts still require explicit non-execution metadata or a contract-error marker. Unknown/invalid local monitor modes are rejected. Evaluation runs continue with `tools=[]` and make no MCP calls or device writes.

Tests use only synthetic read-only monitoring history errors, contrasting unsafe modes and unrelated native tools. No personal source rows or device-specific fixes are added to the repository.

## Acceptance and usage

Run all blocking CI and add-on container checks, merging only when green. On installation of alpha.60, reuse the **same** recent read-only Ask capture or import its private Technical JSON, explicitly approve model data transmission again, and run Compare answers. The original read-only source attempts should remain represented as successful/failed according to the original receipts. A completed replay does not establish the quality of its conclusions.

## Evidence-quality reminder

The frozen review stages have the **same original receipts**. Their purpose is to test whether extra model passes preserve factual provenance and uncertainty—not to discover missing sources or compare V1 versus V2 end-to-end. A later audit can inadvertently omit a useful directly returned source limitation; human scoring must compare the intermediate and final answers against the original evidence. Physical heating status, for example, is not established merely by a hub's reported operating-state transition or a temperature bin with unverified sensor freshness.

Actual live device captures and model answers remain private and are not committed.
