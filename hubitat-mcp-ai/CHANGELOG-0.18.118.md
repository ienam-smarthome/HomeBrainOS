# HomeBrainOS 0.18.118 — Keep real runtime evidence during existing-rule verification

## Reproduced failure

The user's 0.18.117 read-only App 4019 verification retrieved:
- Exact persisted controller settings (backupOffEnabled=true,
  inactiveAction=off, motionOffLockoutMinutes=300 minutes,
  scheduledOffEnabled=false).
- Native Hubitat OFF commands from App 4019 at 16:58:58.691 and
  17:01:16.922, with physical OFF state transitions 0.246s and 0.173s
  later; matching subscribed FP400 and Matter LWR01 inactive edges
  30.058s and 30.269s before those commands.
- An actual Hubitat WARN log from App 4019: method motionHandler ran for
  **129,544ms** at 2026-10-25 16:18:42.628.
- The complete 186,457-character installed Groovy source for code ID 1453,
  paged and coverage-verified by homebrain_read_groovy_source.

The old existing_rule_claim_guard replaced the model answer with a
partial Rule Machine action-tree disclaimer and incorrectly declared
"actual OFF commands" unverified, ignoring the genuine runtime and code
receipts. This conflated *unverified compiled action order* with
*observed executed commands* and hid the long-running app warning.

## Fix

A new generic, bounded projection, keyed by actual verified target app
IDs (not room names or hardcoded 4019), separately renders:
- App-originated OFF commands matched to state changes within 3 seconds;
- App-listener-linked last observed motion inactive-to-OFF intervals;
- App-scoped WARN/ERROR long-handler method durations and unverified-log
  timezone;
- Full contiguous installed Groovy source retrieval **only** when
  sourceRead says fullImplementationVerified, positive character count
  equals declaredTotalCharacters, and source code ID is valid.

The partial existing-rule guard retains its strict "ordered
action/conditions not independently verified" status but can no longer
assert that runtime OFF commands were not observed in the same receipt
set. It does not claim physical vacancy, false occupancy, all timer
branches executed, or code execution correctness from complete source
retrieval. The Groovy source does not turn a custom child controller
into a native Rule Machine action tree.

## Tests

Target-matched synthetic replay of two actual observed OFF sequences,
FP400 and LWR01 timing, cloned/unsubscribed sensor exclusion,
129,544ms warning retention, full source coverage, unrelated app
exclusion, generic alternative controller ID and final API contract.

No writes to Hubitat devices or automation settings.
