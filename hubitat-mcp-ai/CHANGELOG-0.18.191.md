# HomeBrainOS v0.18.191 — Verified command issuers versus driver execution causes

## 28 October 2026 v0.18.190 live test

At 22:31 UTC, a 26.251-second Native V2 investigation of Google Nest Hub (device 7934) completed six of eight MCP reads. The **recovered 50 device events now actually include** two source-attested calling apps:

- 00 Google Calendar Notifier (app 4080): 13 issued commands, eight speak and five setVolume, within the sampled window.
- Adhan Player (app 1679): 16 issued commands, including eleven refresh, three setVolume and two playTrack.
- The Calendar Notifier setVolume event at 17:42:22.698 is one displayed millisecond from the source's 124,842 ms setVolume driver warning at 17:42:22.697.
- 43 sampled runQ warning rows span 17:04:48–17:58:24, but there is no reported command-runQ event in the bounded event sample. This does NOT imply missing app callers: runQ could be a driver-internal callback/queue operation. Its internal mechanism remains unverified.
- The model failed two hub_list_drivers calls, ultimately listed 199 global drivers rather than inspecting the relevant app/device, and the fallback incorrectly said warning-window callers were unverified despite its own explicit app issuer evidence.

## General fix

- Evidence coverage has three separate states: no incident-window commands, a source-attested app command for the exact warned method, or source-attested calling apps during a WARN method that does not appear as an issued command. The third is **driver-execution mechanism unverified**, not **caller unverified**.
- Never generate command-runQ (or command-<any warning method>) as a mandatory direct command if the method is not represented in observed device command events and caller provenance already exists. The model may investigate attested app configuration or driver execution, without asserting the app caused a slow callback.
- A bounded last-chance model prompt prioritises source-attested app configuration over a large driver list for the unresolved internal mechanism. The model still decides what READ to perform; no automatic Hubitat calls or keyword routes.
- hub_list_drivers(deviceId=...) is prohibited at the host operation contract because that global catalogue does not accept per-device scoping. The model receives guidance to use target configuration and attested app IDs instead.
- Final reporting and validation distinguish **driver_execution_cause_unverified** from **warning_window_actor_provenance_unverified**, so supported app-issuer evidence is never described as missing.
- Flattened HTML-rich app labels (e.g. "Adhan Player span style='color:green'") are stripped to the genuine app title, while keeping app IDs and source timestamps.
- New live-shaped tests cover direct setVolume timing, the still-unexplained runQ method, typed callers, correct missing-history behaviour, driver catalogue argument rejection and clean readable names.

## Limits

The log-recorded 147,429ms and 124,842ms durations are driver warnings, not independent CPU profiling. One-millisecond **printed timestamp proximity** does not establish how long an operation had been running, prove clock-zone alignment or assign causation to the automation. The inner driver implementation has not been inspected; raw app source remains outside the native model evidence adapter. Native V2 is experimental, READ-only and separate from production Main Ask.
