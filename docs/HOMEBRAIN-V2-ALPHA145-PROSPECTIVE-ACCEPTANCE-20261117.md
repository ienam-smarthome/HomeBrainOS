# HomeBrainOS V2 alpha.145 — prospective acceptance gate

**Status:** offline gate merged in
[PR #1725](https://github.com/ienam-smarthome/HomeBrainOS/pull/1725) as
`9a6b4e6286d615f866ef8171b1b2e5075c82d2c0` after all four path-triggered
exact-head workflows passed. No new live/model/MCP calls and no quality result.
Runtime alpha.145 remains frozen pending installed capture and independent
source review.

## Why this gate exists

Alpha.135–145 made general causal-source and safe-publication improvements,
but each increment was substantially informed by prior private heating or
causal failures. Exact-head CI verifies engineering contracts, not broad answer
quality. The original `sr-01`–`sr-10` source-real pack was exposed by its
alpha.26 capture and cannot serve as an unseen post-change confirmation.

This gate therefore freezes a distinct ten-question alpha.145 cohort only
after the runtime candidate merged. It covers current hub health, exact
inventory aggregation, multi-device status, lighting causality, heating
causality, installed configuration versus event-time execution, energy
arithmetic, offline telemetry, capability-qualified contact history and
diagnostic-log scope. It includes no answer key, source transcript or private
household identity.

Do not change V2 runtime prompts, routing, evidence recovery or publication
logic after freezing this pack and before collecting it. A demonstrated safety
or build defect may be fixed, but that invalidates the candidate and requires a
new prospective pack for the replacement version.

## In-add-on workflow

Update the Home Assistant add-on to package **2.0.0-alpha.147**. This package
adds the study interface and keeps the answer runtime at **2.0.0-alpha.145**.
The exact-version check still uses the runtime version. Exports record the
installed package version separately. Open **Acceptance study** from the V2
navigation. Supply the same eight exact labels described below and seal the pack, then
select **Capture first answer** once per case. Each button uses the configured
model and a fresh conversation context. The add-on first checks the upstream
per-client grant and then exposes only tools and gateway leaves explicitly
annotated read-only. This capture surface therefore uses a restricted catalog
and its reports identify it as `in_addon_read_only_catalog`. Keep it separate
from normal Ask cohorts.

The original captures and sealed manifest stay in the add-on's private data
directory at `/data/homebrain-v2-alpha145-acceptance`. Use Home Assistant ingress
on a trusted installation. Download individual private JSON files for independent
review. **Run offline verification** checks the saved cohort with the same
verifier below and offers the capture report as a download. Permission preflight
does not count as a study receipt, and offline verification makes no model or
MCP calls. Keep any interrupted case in the study record.

## Private setup (CLI alternative)

Install **2.0.0-alpha.145** and configure a dedicated upstream per-client token
whose `hub_get_info.clientAccess` reports `readEnabled:true` and
`writeEnabled:false`. Do not issue a write merely to probe enforcement. The
receipt is server-reported permission evidence, not an independent penetration
test; the final report deliberately retains
`read_only_permission_independently_verified:false`.

Create a private labels file outside the repository:

```json
{
  "labels": {
    "light": "FIRST_EXACT_LIGHT_LABEL",
    "second_light": "SECOND_EXACT_LIGHT_LABEL",
    "thermostat": "EXACT_THERMOSTAT_LABEL",
    "trv": "EXACT_TRV_LABEL",
    "automation": "EXACT_AUTOMATION_LABEL",
    "metered_plug": "EXACT_ENERGY_DEVICE_LABEL",
    "offline_device": "EXACT_OFFLINE_OR_STALE_DEVICE_LABEL",
    "contact_sensor": "EXACT_CONTACT_SENSOR_LABEL"
  }
}
```

Initialise a new empty private directory:

```powershell
python hubitat-mcp-ai-v2/tools/source_real_acceptance.py init `
  --pack alpha145-prospective-v1 `
  --config "C:\Private\HomeBrain-alpha145\labels.json" `
  --directory "C:\Private\HomeBrain-alpha145\study"
```

The manifest and SHA-256 seal must be retained unchanged. For each
`a145-01`–`a145-10` question, start a new V2 conversation, submit the exact
question once and save the first Technical JSON under
`study/first-answers/<case-id>.json`. Preserve failed, partial and timed-out
first attempts; never replace one with a retry. Raw exports stay private.

At least one successful original `hub_get_info` receipt in the cohort must
contain the connected client's Read ON / Write OFF `clientAccess` block. The
verifier does not retain the client name, token, URL, private labels, raw
question, arguments, answer or log content.

## Offline verification and review

```powershell
python hubitat-mcp-ai-v2/tools/source_real_acceptance.py verify `
  --directory "C:\Private\HomeBrain-alpha145\study" `
  --output "C:\Private\HomeBrain-alpha145\study\capture-report.json"
```

The report identifies missing cases, exact-version mismatches, cross-case
model/version inconsistency, prior-context use, device-command attempts and
permission evidence. It never makes a model, MCP, Home Assistant or network
call.

Only after all ten original captures exist, conduct independent claim-level
source review using the existing
`homebrain-v2-source-real-human-review.v1` format. When `--reviews` is supplied,
the verifier fails closed if any capture is not alpha.145, models/versions are
mixed, prior context or a device-command attempt appears, or the dedicated
client is not source-reported Read ON / Write OFF.

```powershell
python hubitat-mcp-ai-v2/tools/source_real_acceptance.py verify `
  --directory "C:\Private\HomeBrain-alpha145\study" `
  --reviews "C:\Private\HomeBrain-alpha145\private-reviews.json" `
  --output "C:\Private\HomeBrain-alpha145\study\reviewed-summary.json"
```

Human review must separately count factual conclusions, supported factual
conclusions and unsupported definitive causal claims; score source sufficiency
and first-answer usefulness; and inspect exact source identity, clock, filters,
returned/matched counts, paging and causal roles. Successful API completion or
tool execution is not a quality pass.

## Promotion decision

Do not promote V2 on one good case. Report all ten attempts, including failures,
with model fingerprint, version, latency, tool/model rounds and limitations.
Compare the cohort to the permanent targets without converting an incomplete or
unreviewed denominator into success:

- at least 90% grounded evaluated factual conclusions;
- zero unsupported definitive causal claims;
- at least 80% useful complete first answers;
- zero read-only/control safety regression;
- common status latency reported separately from complex investigations.

If the cohort fails, group failures by target identity, schema use, missing
source class, scope/pagination, arithmetic, causal interpretation and
publication. Select one general intervention and evaluate it on another new
prospective pack. Do not tune and rerun this exposed cohort as independent
confirmation.

This gate covers read-only first-answer quality. Existing mocked/native approval
CI remains the safety evidence for write paths; any live control or
administration acceptance requires a separate explicit user-authorised plan.
