# HomeBrainOS 0.18.407 — summary-shape identity evidence and native-claim calibration

## Installed v0.18.406 acceptance (2026-11-05, read-only)

The user submitted the natural-language answer and Technical JSON for the same Rule Machine app 169 native parent-class question on reported add-on 0.18.406. This test **did not verify native class binding**.

- UI elapsed **36.567 seconds**, Gemma Cloud **8 model rounds** (all free), **5 read-only MCP calls**, provider **31.994 seconds**, MCP HTTP **1.705 seconds**. The previous 0.18.405 read had 22.568 seconds / 5 rounds / 3 calls. One non-controlled sample per version is not a proven speed regression.
- The model investigated the relevant app class, but it said app 169 was a **verified native system application** and asserted a type ID of 18. Both current-turn objective requirements remained **checked-unverified**. The answer conflated reported app identity with authoritative native class attestation.
- The model selected hub_get_app_config with `summary=true`; its returned response had top-level **id/name/type/user/namespace** instead of a nested **app** object and omitted `appTypeId`. The v0.18.406 receipt projector accepted only a nested app object with appTypeId and therefore published no typed identity details. Earlier unscoped inventory and type-list reads only produced field-name summaries. This is a proven **public evidence coverage gap**, not proof that the asserted type ID 18 is wrong.
- No modifying tool was recorded. Request provenance still reports model_delivery_verified=false, first_attempt_verified=false and deployed_build_sha_verified=false.

## Generalized correction

1. Project safe, exact-ID-matched scalar metadata for both supported hub_get_app_config shapes (nested full and top-level summary). A missing appTypeId produces a **typed_app_instance_metadata** receipt with only reported values and explicit nativeClassBindingVerified=false, not a false positive class identity. A present, validated appTypeId retains the stronger typed_app_class_identity receipt.
2. Reject mismatched IDs, missing IDs, failed reads, forged nested/top-level ID conflicts, malformed type IDs, and potentially unsafe source fields. Do not publish raw app configuration, arbitrary HTML, endpoint paths, credentials or child listings.
3. At shared read-only completion, only when the native-class proof remains unverified and model prose **affirmatively certifies native identity**, use target-matched public scalar receipts to render a concise, source-calibrated answer. A well-calibrated model answer is preserved. No app or room ID is hardcoded.
4. This release does not solve native Rule Machine parent discovery and **does not unlock Rule Machine writes**. Only a separately authoritative instance→type→native-class mapping could establish native class identity.

The change does not introduce any new network/MCP reads, additional model rounds, or changes to permissions. CI regression tests cover both source shapes, optional missing appTypeId, evidence classification, model overconfidence, preserved correctly negated uncertainty, and mismatched target suppression.

## Post-deployment acceptance pending

Repeat the identical read-only prompt after the 0.18.407 add-on update. Check for a typed_app_instance_metadata or typed_app_class_identity receipt on a target-matched call, correct attribution of reported fields versus independently attested class, and an unresolved native class unless actual authoritative binding exists. Record natural-language answer, Technical JSON, model rounds, tool calls, and elapsed time. Neither runtime improvement nor class attestation can be claimed from CI alone.
