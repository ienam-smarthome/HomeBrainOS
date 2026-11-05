# HomeBrainOS v0.18.414 — targeted read-only native dated-trigger retries

## Final visible-inventory scan (installed v0.18.413, 5 November 2026)

The user's fourth bounded read-only native Rule Machine date scan completed at **offset 36**, examining the final six visible Rule-5.1 children from a stable **42-candidate inventory**: **4206, 4207, 4239, 4241, 4246, 4259**. All six exact-ID `hub_set_rule(operation=read)` trigger/settings document reads verified. The response completed in **4.684 seconds**, without any model round or modifying tool calls.

Rule **4246** contained time-trigger groups **3** at **23:00** and **5** at **06:00**; neither returned `date#` or `atDate#` fields. No enabled dated-trigger field set was established. The four batches (offsets 0, 12, 24, 36) attempted **42/42** visible Rule-5.1 children, obtaining **40 valid native read projections** and **two incomplete rule reads**: **2967** and **3985**. Source visibility and the two incomplete reads prevent proving global absence of existing dated triggers; no authoring proof or writer authorization was obtained.

## General read-only retry addition

- When the user explicitly asks to inspect **existing native dated Rule Machine triggers** by exact `rule IDs` (at most four positive, unique IDs), keep the previously verified dedicated source-typed `native_dated_trigger_discovery` route, but select only those ID-matched visible native child-app records from a newly retrieved inventory page. Do not infer target IDs from unrelated dates, offsets or text.
- After checking the inventory and that a suitable native read gateway is available, use only the existing fully classified `hub_set_rule(operation=read,rule_id,args:{sections:[triggers,settings]})` tool envelope. No native form open, write, creation, execution, deletion or broad rule-health audit.
- Exact IDs absent from that filtered native child inventory receive **no direct document read** and are reported as unverified/absent from returned inventory, not as nonexistent rules. Invalid, duplicate or excessive ID requests are never silently partially executed.
- Return `scanMode=targeted-rule-ids`, `requestedRuleIds`, `requestedRuleIdsNotVisible`, scanned IDs, verified-read state and the same bounded typed time/date evidence. A targeted retry does not return a misleading numeric next offset, does not establish hub-wide absence, and preserves `readinessForMutation=false`.
- Existing offset scans, no-match uncertainty, source-only answer publication and model-driven responses for unrelated questions are unchanged. Targeting is limited to explicit, confirmed visible native child IDs and a maximum of four native document reads.

## Regression coverage and installed acceptance

Tests cover both actual incomplete IDs (2967/3985), one confirmed native read and one mismatched-result failure, missing ID from returned inventory, rejection of incidental dates and excessive/duplicate IDs, unchanged offset scans and preservation of the specialist answer through shared completion. No broader tools, user permissions or writer contract changes.

After updating HomeBrainOS to v0.18.414, retry IDs **2967 and 3985** using the exact bounded read-only prompt. Inspect Technical JSON for `scanMode=targeted-rule-ids`, `requestedRuleIds=[2967,3985]`, and each ID's `readVerified` flag. If both still fail, stop assuming transient failure and investigate the upstream native rule-document response or project a different authoritative, non-form read source. A successful native document read without a saved `atDate#` still cannot authorize Rule Machine date-trigger creation or prove one-shot execution.

No installed v0.18.414 acceptance or timing comparison has been measured.
