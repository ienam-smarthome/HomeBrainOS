# HomeBrainOS v0.18.162 — Model-planning resilience and verified identity reuse

## Evidence from v0.18.161 live acceptance

The user's 27 October dated Bedroom 3 Mesh test recovered the 12 October source-attributed OFF command, matching reported switch=off, and later healthStatus=offline, with two independent historical read sizes and a typed current configuration of issuer 3950. The model still timed out at 35s after 11,379 characters of planning input. End-to-end duration 57.248s, including 21.129s inventory.

## Architecture changes

1. **Freshness- and generation-scoped identity snapshots**. A full, total/unique-ID-validated identity-only inventory may be reused by subsequent opt-in read-only V2 tests for up to 90s in the same process. A mutation invalidates its generation immediately. Returned copies cannot alter cached identities. First/cold requests still perform the full verified Hubitat audit; this is never used to authorise a write or claim a current device state.
2. **Incident-oriented model context**. Cases exceeding 12 observations no longer send every repetitive background telemetry sample to the LLM. Command issuances, switch/health transitions and typed stored controller settings remain individually retained. First/last background samples and source coverage are represented with omitted counts. The immutable source case/report is unchanged.
3. **Bounded optional advisory planning**. When a *source-attested* OFF/state/adverse-state relation and typed stored controller configuration are already present, remaining model planning is limited to 15 seconds (or the caller's stricter bound), preventing repeated 35-second waits for what is now an optional supplementary analysis. The original model budget remains for cases without the relevant discriminator. The model cannot grant read/write permissions. Time budget class is exposed in diagnostics.
4. **Correct stored-setting attribution**. A config observation has a verified app target ID but no event producer; report it as Controller app #ID (or an independently known current app label), not “Source not identified”. Current stored settings are not inferred historical settings.
5. **Exact single-day timezone handling**. V2 now invokes the authoritative Hubitat timezone resolver for a single specified calendar day as well as ranges and relative dates; the explicit incident window still records UTC source boundaries and preserves BST/GMT source times.

## Tests and safety

Synthetic regressions cover medium-case model compaction, source ID and settings attribution, 12 October UK BST boundaries, optional model budget, identity-cache copy isolation and mutation invalidation. Existing confirmation and read-only gates remain unchanged. No actual Hubitat actions were executed during development.

## Limits

- A slow configured LLM/provider can still fail to return a structured plan; the shorter advisory timeout does not make it reason like a faster provider. The deterministic evidence-based fallback remains explicitly tentative.
- Cold full identity inventory may still take ~21 seconds. The improvement applies to subsequent verified read-only V2 requests in the TTL and same add-on process.
- The 12 October OFF → switch-off report → offline sequence does not by itself prove the network topology or physical mechanism.

## Live acceptance

After updating to v0.18.162, run the same dated read-only investigation twice within 90s and inspect identity_inventory_ms, inventory_page_diagnostics.mode, planning_diagnostics.input_chars, budget_policy, stopped_because, and report settings attribution. Do not change devices or apps. The second run can use a verified identity snapshot only while its generation is unchanged.
