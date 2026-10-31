# v0.18.269 — V3 model-led upstream frontier: runtime handoff and typed dependency receipts

## Live acceptance failure in v0.18.268

Read-only Bathroom replay confirmed correct 5/5 ON and 5/5 OFF sensor 7895 collector-reception matches and improved digest accuracy, but the model checked **light** dependents rather than **sensor** dependents, spent time on an unrelated stale whole-hub log read, and ended without tracing 7895 to an app. Metrics: 23 tool calls, 11 rounds, 61.9 seconds; 6 model claims supported and 1 rejected, so digest publication remained the safe choice.

## Diagnosed architecture defect

The historical journal checkpoint is emitted only when it recovers new archive rows. The read feasibility planner requires a successfully observed dependency leaf before it can name a concrete model-selected READ. On the live trace, input archive recovery occurred before any dependency read was known to be available. Later successful target-dependent reads did **not** cause a fresh model-visible checkpoint; the next model round was free to continue into unrelated logs. Separately, a successful dependency tool response was represented in evidence receipts by its field names rather than its structured `appsUsing` app IDs, preventing deterministic shared-app lead nomination.

## Changes

- Introduce a pure `ranked_upstream_continuation_checkpoint` from existing evidence receipts. If the source-qualified input frontier becomes feasible after a later read, offer an evidence-ranked, model-selectable READ in the next **already allocated** investigation round; dedupe repeated offers by exact leaf+args.
- Preserve no new permissions and no host-chosen tool invocation: the live catalog and model still authorise and select READs.
- Capture only verified positive numeric app IDs from successful `hub_list_device_dependents` results that explicitly match the requested device ID. No app name, arbitrary metadata, configuration, secrets or device commands are persisted.
- An app-config lead still requires **both** input and target dependency lists to explicitly contain the same app ID and no previous exact attempt.
- Add `v3_ranked_upstream_round_offer` counter to show the handoff actually reached the model.
- Include regression fixtures for late leaf availability, input->shared-app escalation, failed/previous attempts, incomplete archived input, missing switch pairing, and whitelisted ID projection.

## Safety and next acceptance

One observed receiver-clock association is not original sensor event order. A current app association is not historical app execution. An original ON issuer remains unverified without independently recorded command provenance. The guarded digest publication boundary and typed-claim attestation are unchanged.

After installing, rerun the identical read-only Bathroom request, confirm the `v3_ranked_upstream_round_offer` counter and a subsequent `hub_list_device_dependents(deviceId=7895)` call. Check whether an actual shared app ID is in the successful receipts; do not claim root cause merely from a dependency match.
