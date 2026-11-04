# Q2 — first actual local Early Heating OFF pair, source-based review (4 Nov 2026)

## Actual completed experiment (not a production control)

The user locally executed the Q2 private first-answer capture for the frozen
synthetic/anonymised case `aq_early_heating_off_resume`. It completed
with exactly one request per local model, without Hubitat/HA tools,
device mutations or Cloud model usage. The user provided complete
plaintext first answers and both metadata manifests.

Frozen packet SHA-256:
`cb5153f5d4beb82491c34b619d8e64f8f46bec86962533db38ffb4124e8a3bb1`.
Both run metadata records carry local checkout build SHA
`7e81e0411b50f814241a64c2406f7fe908fa95fd`
and `attempt_index=1`; these are tool records, not
independent attestation of model/server identity or physical devices.

| Arm | Provider/model | First-answer latency | Exact raw answer SHA-256 |
| --- | --- | ---: | --- |
| Baseline | `ollama-local` / `qwen3.5:4b` | **22.672s** | `ea47ab547ef37fc6cc61e73f3cb8b46c312fc335451650cd9d41143988b0cb66` |
| Candidate | `ollama-local` / `llama3.2:3b` | **6.406s** | `3da98ab387346a8b666f36b35ecdb0e63e9431be3d701658518b4a44b8ca9f1e` |

Both SHA-256 hashes were independently reproduced from the
exact pasted response texts **after correcting only the terminal
mojibake**: PowerShell displayed the UTF-8 `°C` sequence as
`Â°C`. The corrected `°C` bytes **exactly** match the
private first-answer digests (UTF-8, LF, no trailing newline).
The original private files are not modified or committed.
For a Windows display check use
`Get-Content -Encoding UTF8 -Raw <path>`; this changes
text decoding for display only, not model answers or hashes.

The Llama request completed **16.266 seconds faster**,
about **71.7% less model-request wall time** for this
one local frozen case; do not extrapolate to a p95
or end-to-end HomeBrainOS latency distribution.

## Ground truth and preliminary qualitative assessment

The fixed registered case provides exactly three facts:
(1) a temporary Early OFF command lowers a selected
thermostat/TRV target to **12°C**; (2) a 30-minute
timeout was observed restoring **22°C**; and
(3) independent demand coordination/protection may
subsequently inhibit or request heat. The required
answer must distinguish setpoint state from
**actual boiler firing**, which is not established
by either source fact.

**Qwen 3.5 4B:** Correctly reports both setpoint
values, the observed 30-minute restore, and
the possibility of independent demand/protection.
However, it invents explanations that are not
in the frozen packet: 12°C as a *frost-protection
safety floor*, and the 30-minute timeout as
a *heartbeat* to ensure normal operation
re-engages. These are worded as possibilities
but are not source-verified. The response
never explicitly says that changing/restoring
a target temperature does **not** establish
physical heat demand or boiler operation.
Its label "external interference" also
risks portraying legitimate independent
demand-control logic as an anomaly.

**Llama 3.2 3B:** Its entire saved first response
says only that early heating OFF reduces the
setpoint to 12°C. The statement is supported
by the packet, but it omits the **30-minute
restoration**, separate demand/protection
behaviour, physical-execution limitation,
and an actionable next read. This is an
extremely incomplete response, not a
successful useful answer simply because
the API returned text and a digest.
The raw capture manifest did not retain
Ollama `done_reason`; do not infer
whether this one-sentence response stopped
normally or was internally cut short.

**Matched-source reference explanation:**
"A temporary Early OFF request lowers the selected
thermostat/TRV target to 12°C. The observed 30-minute
timeout restored it to 22°C. This is a setpoint
restoration, **not** independent evidence of the
boiler stopping or starting. A separate demand
coordination/protection system may still request
or inhibit heat; physical operation needs
independent status or actuator evidence."

This assistant assessment is an **initial,
non-blinded qualitative review** against the
versioned source fixture, **not** a completed
SHA-bound human-review scorecard or an
aggregate factual-grounding percentage.
Neither output supports declaring a
production routing winner. Llama was
faster, Qwen was more complete, and
both had important quality limitations.
No production HomeBrain add-on code
or model settings were changed.

## Next Q2 evidence and engineering direction

Complete the final untested frozen
`aq_rule_parent_type_gap` case on the
same local pair, **one case in a fresh
private folder**. Review direct source
type identity versus display-name claims:
app instance 901 is only a candidate
when type catalog id 718 is omitted.
Then compare all actual local results
across MQTT, causal command attribution,
heating and native Rule Machine identity,
with a separately disclosed human rubric
before any provider/answer-layer change.

Avoid single-answer publication
patches, unverified physical heating
claims, silent retries, and Cloud
calls without separate opt-in.
Keep HomeBrainOS add-on v0.18.404
and existing automation settings.
