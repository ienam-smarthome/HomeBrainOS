# HomeBrainOS v2 — causal reasoning acceptance (alpha.33)

This is a **read-only evaluation procedure**, not a hidden runtime instruction,
a device-specific patch or a claim that a single passing example proves model
quality. The original MCP receipts and user question are the evidential basis.
Do not publish private device or home data in this repository.

## What changed

The production model receives `skills/hubitat/causal-investigations.md`
alongside the existing Hubitat skill. The reference asks the model to test
*why* claims against time, competing hypotheses and available discriminating
sources. It does **not** change model/tool routing, agent deadlines, source
filtering, thresholds, device authorisation or answer postprocessing.

## Evidence-first review checklist

For each new, varied *first answer*, record:

1. **Focal event and time** — source event timestamp, timezone, and what was
   observed (state report, issued command, sensor sample or app log).
2. **Source coverage** — exact `since`/`until`/limit and rows returned. Empty
   bounded queries are not proof of absence or historic continuity.
3. **Reporter versus actor** — who issued an actual command versus who reported
   a state and which app merely listened to that event.
4. **Current versus historical settings** — note the timestamp of an app-config
   read; do not silently backdate the configuration to the focal event.
5. **Temporal predictions** — when an explanation asserts a delay or timer,
   calculate the time at which the alleged trigger would have to occur under
   the stated semantics; compare it to source observations and lookback.
   Missing evidence is not a contradictory *observation*, but cannot verify
   the start. Where a candidate is inconsistent with observed chronology,
   reject or qualify it.
6. **Discriminating alternatives** — ask what could distinguish a normal
   timer from a backup, retry, manual intervention or external command.
   Consider only mechanisms supported by configuration/evidence. Don't call
   an explanation the **only plausible cause** unless alternatives are
   actually addressed and excluded.
7. **Outcome** — clearly label event, command origin, mechanism compatibility
   and event-specific cause as separately verified/unverified.

### Cross-domain acceptance scenarios (fictional examples)

These examples describe evaluation concepts, not commands or hardcoded
incident logic in production.

| Scenario | Evidence challenge | Acceptable conclusion |
|---|---|---|
| Timed ventilation | An OFF command follows an unverified countdown; a narrow humidity-event query has zero rows. | Controller's recorded command may be verified, but timer start and specific trigger are not; look for preceding states/logs before claiming a cause. |
| HVAC demand | Current zones are idle, but historical controller activity is queried. | Do not infer earlier heating demand from current snapshots; inspect historic participating zones and coordinator configuration, report any missing zones. |
| Power telemetry | Power drops to 0W but switch remains on and voltage is missing. | Zero consumption is not proof of an electrical outage. Identify a discriminating voltage/supply report, or leave outage unverified. |
| Positive control | Recorded trigger, controller execution record and state report are mutually consistent in the same timezone and event window. | State the supported event-specific cause confidently within the verified scope; avoid unnecessary extra reads. |
| Bridge/automation attribution | Physical state is reported by a bridge and app appears only in `triggered[]`. | Do not turn a listener into an initiator. Seek a command or execution receipt if the issuer matters. |

## Ratings and decision rule

Score *factual grounding*, *source completeness*, *causal calibration* and
*usefulness* **0/1/2**, using n/a only when truly inapplicable.
Compare against **original successful MCP receipts**, not the answer's own
claims. Record successful/failed tools separately, including timeouts and
truncated source results.

The release gate checks that the guidance loads and the original model-led
tool loop still works. It does **not** run the configured cloud model or prove
better first-answer accuracy. Actual acceptance requires diverse, new
first-answer Technical JSON reviews with both plausible-but-unverified
mechanisms **and** genuinely supported positive causes.

Do not modify Hubitat, Home Assistant, or external records to manufacture
evidence. Do not add a fix tied to one device ID or one incident.
