# HomeBrain 0.17.47 — Cross-source historical event reconciliation

## Live 0.17.46 observations

Current lockout configuration lookup is now verified at ~300 ms with 1 read call, versus 11 s and 0 calls before. App 4019 currently exposes `motionOffLockoutMinutes=300` while user's intended duration is 3 minutes. Trigger mode and button ID were not returned in that persisted settings payload; never assert they were verified from the present configuration.

The 12 October 23:49:27 BST reconstruction correctly anchored native logs at 22:49:07–22:52:42 UTC, and found button 746 plus a journal light OFF. But the final model incorrectly reported **no app 1251 command was verified**, while the native device command stream already contained **app 1251 command-off at 23:49:27.336 BST**, and the native button stream retained button 746 pushed at 23:49:27.303 BST. The **native light switch-state stream did not retain the corresponding 12 October OFF in this new request**; a Historical Journal *collector-received* OFF at 22:49:28.623 UTC is separate corroboration, not the native state event clock. FP400 Computer Desk motion was journal-received at 22:49:33.826 UTC with no verified activation role.

## Improvements

- Add `focal_event_cross_source.py`: join physical controller/button number to producer-labelled native OFF command, then independently associate a journal collector-received OFF for the exact light and bounded timestamp. Prevent joining wrong button numbers, wrong devices, or stale event times.
- Preserve native button and command timestamps separately from Historical Journal receipt time. **Never assert native OFF-state or app 4019 execution proof solely from that journal observation.**
- When source-reconciled collector OFF exists, surface bounded post-OFF motion observations without promoting the sensors to eligible activation sources.
- For explicit historical focal events whose native switch row is no longer retained but independent controller, app command, journal state and scoped app logs were read, finish with **one evidence-bounded synthesis** instead of triggering further unrelated model tool searches. Counter: `lockout_cross_source_sufficiency_stop`.
- Add regression tests for live event timings, mismatched buttons, wrong devices, source clock degradation, source absence, native state vs collector receipt, and prefetch-to-synthesis readiness.

## Safety, provenance and remaining unknowns

Read-only: no Hubitat automation, rule, device, controller or setting is changed. Existing app 4019 duration remains 300 minutes. App 4019's actual historical lockout decision remains unverified when scoped app logs are empty; neither later motion nor the absence of a subsequent ON proves an effective lockout. Collector journal gaps prevent exhaustive negative statements about motion or device state. Native causal command provenance does not itself prove the historical app 4019 lockout logic.
