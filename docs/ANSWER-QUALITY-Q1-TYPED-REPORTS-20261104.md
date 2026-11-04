# Q1 field-attested status reports — 4 November 2026

## Actual user-observed baseline

Registered read-only question: `What is the hub health status?`
Installed HomeBrainOS: **0.18.400**. Response took **11.139 seconds**,
two Gemma 4:31b free rounds and one tool call. The single successful
`homebrain_hub_info_snapshot` receipt reported resource figures and
driver states. Values in the natural answer that were supported by
that read include CPU five-minute 0.78 / 19.5%, free memory 756.39 MB,
DB 175 MB, uptime 0d:18h:33m:54s, firmware installed/available
2.5.3.117, Zigbee enabled with healthy=true, Z-Wave disabled, and
Matter online. The model also asserted **temperature 42.5°C** even
though the typed `reported` source had **no `temperature` value**
(only `temperature_unit=°C`). It stated **'healthy with no active
alerts'** without a comprehensive alert read, and described firmware
as externally **'up to date'** solely from matching driver versions.
Those claims were not established by the source scope.

A separate later Hubitat UI screenshot of the Hub Info C8 Pro device
showed CPU five-minute 1.36 / 34.0%, free memory 782.07 MB and DB 177.
This is a **different later saved-state observation**, not evidence
that the earlier resource fields were wrong or the model fabricated
them. The screenshot is partial and cannot establish whether the
driver ever exposes temperature lower in its current-state list.
The checked earlier API snapshot did not report temperature. The
UI's 'Cloud invalid endpoint' also does not independently prove an
active system alert or failure of an unused optional cloud service.

## General mechanism — no device-specific patches

A successful typed source response does not imply every field exists.
The ordinary read-only answer fast path previously skipped the
investigative synthesis validator and allowed any precise natural
metric or overbroad health claim. The fix adds a shared, final
model-independent **field-attestation boundary**:

- Read only successful, nonmutating, current-request, identity-typed,
  scope-matched evidence (`reported` fields or per-device
  `reportedDeviceState.reportedAttributes`). Do not reread the hub.
- Compare *claimed* numeric status values to actually present values,
  with explicit source identity and unit checks. A `_unit` field
  never becomes a measurement. Handle hub resource, lighting, power,
  humidity, battery, temperature and other mapped sensor attributes.
- Reconcile checkable status words with the source's reported states
  (e.g. 'enabled' is not the same assertion as 'online').
- A successful refresh or cached source scalar cannot prove complete
  alert absence, physical endpoint health or external firmware freshness.
- Do not merge independent devices. If multiple reads conflict for
  the same identity without source-event time, abstain from choosing
  one as if current. Never use a previous answer as a source.
- Retain the original natural-language model answer and modify only
  demonstrably contradicted or unsupported assertions. Log private-
  data-free correction counters; no new LLM rounds, tool authority,
  driver requests, Hubitat writes or special cases for IDs.

## Measurement and acceptance

Before v0.18.401: observed unsupported 42.5°C, overbroad 'healthy
with no active alerts', external firmware freshness claim. Runtime
11.139s, two model rounds, one source call. Formal first-attempt
verification flags false; no population accuracy rate may be claimed.

After v0.18.401: **NOT YET MEASURED ON INSTALLED BUILD**. CI synthetic
tests must establish numeric claim matching/missing, two-device identity
isolation, conflicting source snapshots, ordinary Markdown prose and
read-only/effect boundaries. Repeat exact registered hub-health question
on a new topic and return first full answer and technical JSON.
Check that all presented values exist in the actual typed response,
no missing temperature is fabricated, no overall-alert audit is
claimed, no 'enabled' radio is upgraded to physical online, and
the response remains natural and below 15s where possible.

Regression risk/rollback: if a valid typed numeric assertion is
rewritten incorrectly, if identity checks conflate devices, or if
the status validator leaks raw private source values, roll back
the general guard. No runtime Q1 source has yet proven model parity
with Claude or 90% grounded conclusions over a representative set.
