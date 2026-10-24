# HomeBrainOS 0.18.91 — Source-level hub-load causality calibration

## Observed 0.18.90 live regression, 24 October 2026

An app-source investigation for Device Status Report, installed **App 3977** (source code **1410**), successfully retrieved 81,240/81,240 Groovy characters and discussed `publishReportToDevice` invoking `reportDisplayDevice.setReportData(reportText, offlineCount, lowBatteryCount, motionCount)` near line 820. This was an improvement over previous off-topic answers.

However, Gemma then asserted that Hubitat `LimitExceededException` *typically* means a string exceeded a Zigbee/Z-Wave packet, character, protocol or driver buffer limit, and proposed a large `reportText` as a **high-confidence** mechanism. That conclusion was not backed by a driver-source read, matched device identity or packet-size measurements. The earlier actual error text identified **App 3977 generating excessive hub load** at `setReportData` line 64, not a confirmed transport payload overflow. Long average execution time also does not establish a waiting/timeout mechanism.

The 0.18.90 report marked methodBodyCoverage as **not-certified**, `questionResolved=false`, and `device_logs` missing. Its bounded App 3977 `hub_get_logs` query returned zero rows; no current-turn Device 7182 query was made, so absence of errors is not established.

## Fix

- Add a small **source-code-domain causal guard** that corrects positively asserted but unsupported packet-size, Zigbee/Z-Wave, buffer and timeout explanations in answers involving `LimitExceededException` unless driver source was explicitly retrieved. Preserve verified call sites, measured performance observations, the model's correctly expressed uncertainty and known code/source limitations.
- Apply the guard during pre-repair `validate_synthesis` and again at **API serialization** in case the model revision reintroduces the unsupported cause. Return stable `source_unsupported_payload_limit_cause` / `source_unverified_wait_causality` labels in `evidence_validation.source_exception_mechanism_calibrated` when correction occurs. All other investigation domains retain existing behaviour.
- Update source-directed final-model instructions: excessive **hub load** is not automatic proof of packet-size overflow; `averageMs` is not proof of a device-response timeout. A call made via a device reference does not independently establish the concrete device ID or the content of its Groovy driver.
- Add regression tests replaying the actual 0.18.90 false mechanism, retaining a source-backed call site, accepting correctly cautious statements, skipping cases with explicitly verified driver source, validating synthesis and validating API output.
- Preserve the source-completion gate: a whole Groovy file with no confirmed target-method body and missing current-turn device logs **does not** establish the historical overload root cause.

## Scope and limits

This patch stops a particular class of unsupported source-level causal claims. It does **not** retrieve Device 7182's actual assigned driver source, prove the precise `setReportData` implementation or demonstrate whether report generation frequency, event emission, loops, synchronous work, a hub-global condition or another cause produced the prior exception. These remain investigation tasks, not settled findings.

No Hubitat live app/driver/device/rule changes, no write commands, and no paid model routing changes.
