# v0.18.325 — Stage 9.1 verified issuing-app decision shadow

## Real live observation
On 1 November 2026, Command Shadow for Hallway Light 1 (device 7829) showed a **source-recorded command-off** attributed to numeric app ID 4012 at **13:32:59.835 UTC**, and a subsequent OFF report at **13:33:00.131 UTC**, an apparent difference of **296 ms**. A total of 13 switch reports and six ON→OFF report pairs were in the read. The command issuer's upstream trigger, actual device execution and unique cause of the OFF state were not established. Other OFF reports lack returned command provenance.

## New separate, consented follow-up
- After the existing Command Shadow result contains exactly **one** OFF command with recorded issuing app ID, the phone offers an additional **separate consent** checkbox and **Investigate recorded OFF command's app decisions** button.
- The backend accepts only the numeric device ID, exact UTC command time from the prior source display, and explicit consent; it never accepts a caller-selected app ID or tool name.
- The server performs one fixed, target-scoped `hub_list_device_events` read restricted to `command-off` and a 50-record cap, then matches the **exact recorded UTC time** and unique source-reported app producer before requesting any logs.
- A command row with an explicit matching device ID is stronger than a row relying solely on the backend's device filter; distinguish these identity bases. Wrong-device rows fail closed.
- Only after an unambiguous source-authored app ID is found, request exactly one **read-only** `hub_get_logs` operation under `hub_read_diagnostics` for that app ID, with `since` and `until` fixed to **±2 minutes** around the verified command and a maximum of **100 log records**.
- Release only bounded timestamps, deterministic app-decision classifications, source identity basis, aggregate counts and missing-evidence caveats. Never return untrusted raw private log messages, app/device labels, tokens or source descriptions.
- Treat log declarations as **reported text**, never proof that a specific timer, motion sensor, button, automation branch, device action, or physical transition actually occurred.
- Fail closed for missing/ambiguous/expired command records, mismatching explicit issuer IDs, malformed envelopes, cross-origin/missing consent, and exhausted app logs.
- No Ollama Cloud calls, device commands, change of journal capture/retention or production publisher activation.

## Manual acceptance
Upgrade to v0.18.325. Run **Live Shadow → Command Shadow** for device **7829** and UTC date **2026-11-01**, tick its consent. If an attributable OFF command remains visible, the separate **Stage 9.1 app-decision** follow-up appears. Tick its distinct consent and run once while the incident remains within **48 hours** of current time. Expect either classified, scoped app-log declarations or a meaningful no-source/no-classification status. A missing or unclassifiable log result cannot prove the automation was idle.

If the original command has moved out of the bounded page, do not repeatedly query it. Capture a new naturally occurring recent incident instead. Do not modify live devices.

Rollback: revert PR to v0.18.324.