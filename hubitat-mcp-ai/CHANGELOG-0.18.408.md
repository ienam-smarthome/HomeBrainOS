# HomeBrainOS 0.18.408 — source-verified app identity answers

## Observed installed 0.18.407 acceptance (5 November 2026)

A real read-only native-parent identity question for an installed Hubitat app completed in **19.139 seconds** with **5 free Gemma Cloud rounds**, **3 MCP read calls**, and **15.427 seconds provider time**. The real v0.18.407 transcript now included a valid `typed_app_instance_metadata` source receipt, improving on previous untyped field-name-only responses. It reported:

- target-matched app ID, a safe reported label and name;
- `parentAppId: null`, explicitly a *reported* parent field rather than independent native-parent certification;
- **42 child-app rows in the returned page**, which is neither proof of 42 complete rules nor of their child types;
- no validated numeric `appTypeId`, `reportedSystem`, `reportedType`, or `reportedNamespace` in this specific typed receipt.

The model answer was still labelled unresolved but asserted that `system: true` was explicitly marked, said there were **41 child rules**, and claimed all child rules were `Rule-5.1`. These assertions are **not certified by the published typed receipt**. The difference between 41 claimed rules and 42 returned child-app rows is not itself proof the model read the raw payload incorrectly: rows can include entities besides rules. The public answer did not distinguish that possibility, and the public receipt does not establish the rule total or types.

The previous installed samples of 22.568 seconds (v0.18.405) and 36.567/52.189 seconds (v0.18.406) are observations, not controlled speed benchmarks. The native class relationship remains **unverified**, and request provenance still lacks first-model-delivery and deployed-build-SHA attestation.

## General correction

- For the **app_class_identity** question domain when independently authoritative class binding is still incomplete, compile a **readable final identity answer only from existing target-matched typed receipt fields**, rather than trying to detect individual unsupported model phrases with ever-broader regexes.
- Match both the actual `hub_read_apps_code / hub_get_app_config` operation and its explicit requested app ID to the typed reported app ID. Reject unrelated, unscoped, malformed, conflicting or modifying receipts. A summary-kind receipt cannot silently supply a numeric type ID.
- Preserve distinct **reported metadata vs native-class proof**. If child-app row count is available, label it as **rows returned in a page**; it never implies that the rows are all rules, all of a specific version, a complete inventory, or that the app is an authoritative native parent.
- Expose `appIdentityPublication.mode=bounded-source-identity-publication` in Technical JSON and count `app_identity_source_publications`. The model still chooses reads and investigates; this narrow fact-certification boundary prevents model-only specifics from being published as source-backed findings.
- If no matching typed receipt exists, return a concise evidence limitation rather than inventing a name/type/parent. If an independently verified native-class contract is eventually available, model prose can be preserved through that separately validated route.
- No new MCP reads, model rounds, writes, extra permissions or rule-creation capability. No device or rule is modified by this change.

## Validation and future live test

Tests cover mismatched app IDs and read arguments, partial summary receipts, conflicting reported flags, child row counts versus model prose, unsupported child types, multiple named app targets, source-only reporting despite a nominally cautious model answer, and shared completion metadata.

After updating the installed add-on to 0.18.408, repeat the identical **read-only** parent identity question and review natural answer + Technical JSON. The expected response may verify source-reported name, explicit parent field, and bounded child rows; it must not assert a system flag, a numeric appTypeId, child rule count/type or authoritative native class unless supported by independently verified typed evidence. The real runtime impact of v0.18.408 has not yet been measured.
