# HomeBrainOS 0.18.86 — Link device-originated app errors without claiming throttling

## Observed 0.18.85 read-only audit (23 October 2026, 23:10 UTC)
- Comprehensive audit completed with `gemma4:31b` verified on Ollama Cloud, using the Free tier, and successfully read the three requested app IDs.
- App 3977 (Device Status Report) was present in the top-20 performance sample (`averageMs=107090.14`, `pctBusy=10.6`). A direct `hub_get_logs(appId=3977)` returned **zero rows**.
- The independent `hub_get_logs(deviceId=7182)` returned **24 device-originated ERROR rows** whose messages explicitly named **App 3977** and `LimitExceededException: App 3977 generates excessive hub load on line 64 (method setReportData)`.
- Gemma correctly reconciled these two sources in its narrative, but the deterministic **Requested app checks** section did not associate App 3977 with the errors and could mislead readers. The model also overclaimed that the exceptions prove active throttling and system-wide instability; that an offline mesh is definitively unable to receive commands; and that high average call time causes observed exceptions.

## Changes
- Cross-reconcile exact **numeric app ID** from bounded, successful **device-sourced** ERROR/WARN group summaries containing `LimitExceededException` and `App <ID> generates excessive hub load`. Retain the separate app-scoped zero-row receipt. Include emitting device ID, count of **observed log rows** (not independent incidents), and timestamp-coverage limits; never convert a device-sourced row into an app-source row or assert current root causation.
- Ensure the reconciled section is rendered before optional AI analysis and supplied as bounded audit evidence.
- Tighten optional AI instructions and source-scoped correction patterns: exception presence does not verify active throttling, impact on other apps, individual command failures or the causal relationship between average execution latency and overload.
- Add replay regression tests for the exact App 3977 / Device 7182 mismatch, alternative app IDs, failed reads, preserved source count and cautious AI wording.

No Hubitat commands, app/rule changes, saved-option changes, paid routing changes or hidden background monitoring. This release does not establish the underlying root cause of App 3977's excessive-load exceptions.
