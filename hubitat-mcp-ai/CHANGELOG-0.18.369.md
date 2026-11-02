# HomeBrainOS Hubitat MCP AI v0.18.369 — native inventory evidence and completion semantics

## Real installed baseline

On 2026-11-02, v0.18.368 answered the identical read-only Rule Machine parent / one-time rule inventory question in **2.667s wall**, with **3 Hubitat MCP reads**, 4 total evidence receipts including the host-typed projection, **zero model rounds**, zero confirmation requests and no modifying tool receipts. This is much faster than v0.18.367's 44.626s and 9 model rounds, but is **one case, not a measured median**. Current Hubitat source included a Rule Machine-labelled app instance ID **169**, no verified appType ID/namespace join, and **zero** exact `(One-time YYYY-MM-DD HH:MM)` suffix matches in complete reported app/rule listings. No surviving matching rule is not historical proof that the earlier one-time authoring never worked, nor a substitute for verifying a dated native reference.

## Identified defects

- App type/instance class ID joins can be absent on live Hubitat. The upstream MCP installed-app tests explicitly permit `appTypeId=null` on otherwise valid instance records. It is correct not to certify parent ID 169 as an instance of native built-in Rule Machine without a typed source link, but the answer/diagnostics previously failed to say which field was missing.
- Final `shared_investigation_completion` incorrectly reapplied the **existing_rule_verification** action-tree, rule-health, and dependency obligations to a factual Rule Machine inventory request despite a host-typed parent/list projection. This added irrelevant Technical JSON fields and made the status harder to interpret.

## Change

- Preserve bounded, non-secret source diagnostics for the candidate Rule Machine instance: source app ID, source appType ID when present, verified native app-type class IDs and a reason `instance-appTypeId-absent` or `no-matching-native-app-type-id`. Never infer parent ID from a name or child-count agreement.
- When a successful, nonmutating `typed_native_rule_inventory` receipt matches the expected source contract, completion uses dedicated domain **native_rule_inventory** and only the requested native-parent identity, exact suffix match inventory and optional native-document proof if requested and a match exists. It does not require ordered actions, rule-health or runtime causal proof for an inventory question.
- Partial outcome remains **Unresolved** when native parent identity cannot be verified, even when exact suffix absence is confirmed from complete current listings. Full evidence and type join may mark the inventory complete without a model call. Previous errors/failures are never automatically converted to success.
- No additional Hubitat calls, rule writes, source access, confirmations or model rounds are introduced. Native one-time rule compiler remains offline and non-executable.

## Evidence, tests and limits

Synthetic tests cover the actual v0.18.368 `appTypeId`-missing shape, successful exact ID/namespace join, incomplete pagination, ambiguous user-owned type, untrusted/mutating receipt exclusion and restricted diagnostic fields. The tests and all-green CI verify code paths only.

**Actual installed v0.18.369 answer and current parent-link diagnosis: NOT MEASURED.** Further authoring work still requires a direct native parent relationship and a real dated one-time source or independently proven native date semantics, with fresh per-write consent. Rollback: revert these scoped inventory diagnostics/completion changes; retain v0.18.368 safe read path.
