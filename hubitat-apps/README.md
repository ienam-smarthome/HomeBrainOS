# Google TV — Cumulative Internet Allowance

Standalone Hubitat user app source: google-tv-cumulative-allowance.groovy

This is source only. A HomeBrainOS add-on update or GitHub merge DOES NOT
install, enable, or update the app on Hubitat.

## Required behavior

- TV smart-plug ID 4221 switch ON accumulates usage across separate sessions.
- TV OFF pauses counting without resetting prior minutes.
- On reaching 3,600 cumulative seconds, request Internet control 6923 OFF
  and verify the reported switch state. Never automatically unblock it.
- An observed Internet access OFF-to-ON switch transition resets to zero and
  grants another hour; if TV is ON the timer starts immediately.
- Preserve elapsed checkpoints in atomicState across hub restarts; no daily
  reset. Checkpoint once per minute while counting.
- The installed app starts disabled and requires selection of exactly the
  specified IDs, plus separate enable and shared-control review checkboxes.

## Important limits

Manual versus automated unblocking is NOT distinguishable from the ordinary
switch event. Either kind of OFF-to-ON transition starts a fresh allowance.
A manual-only reset would require verified command provenance or a dedicated
reset button; do not label this behavior manual-only.

Existing rule 3985 is different and is not changed. If it also blocks or
unblocks Internet control 6923, the two automations may compete. Do NOT enable
this app until its interaction with rule 3985 is reviewed. The required
conflict-review checkbox makes this an explicit deployment choice.

The latest live TV meter showed 88 W during viewing, but standby wattage is
not yet established. This implementation deliberately measures the power
socket switch ON, not true viewing time or a power-watt threshold. If the
socket remains ON while the screen is in standby, that time counts.

The block path uses the switch OFF command and verifies the reported switch
attribute. It does not prove actual network reachability. Optional device
commands such as blockInternet, allowInternet, addTime and resetUsage were
not used because their effect semantics remain unverified.

A power outage or abrupt reboot can discard the last uncheckpointed minute;
the app does not count unverifiable hub-offline time. Unexpected timer gaps are
limited to 120 seconds. A failed block is retried at most three times and an
error is logged rather than claiming success.

## Installation — requires explicit approval

1. In Hubitat, open Apps Code, choose New App, paste the source and save it.
2. Open Apps, then Add User App, and select this app.
3. Select device IDs 4221 and 6923 in the app settings.
4. LEAVE the Enable blocking setting OFF during initial review.
5. Check existing rule 3985 and any other controls for device 6923.
6. Review the current switch attributes; verify the OFF = Internet blocked
   convention on the actual installed device driver.
7. Only after explicit permission and testing, enable blocking and confirm
   shared-control review in settings.

## Manual acceptance tests before production use

- Incorrect device IDs: no action.
- Disabled controller: no block even when TV is ON.
- TV ON 20 min, OFF, ON 25 min: 45 min consumed, no block.
- A further 15 min: block requested, Internet switch reports OFF.
- Internet switch restored ON: counter resets, fresh 60 minutes begins.
- Duplicate ON event without an OFF: does not reset.
- Hub restart: saved minutes retained and resumed; outage not backfilled.
- Failed OFF command: visible error and bounded retries.
- Existing rule 3985 unchanged and no unexpected re-block loop.

Tests in tests/test_google_tv_allowance_source.py are STATIC safety-contract
checks and a Python REFERENCE MODEL; they do not execute or compile Groovy.
No physical Hubitat integration test has been performed. Never describe the
app as production verified before the above tests have actually run.
