# Q2 — first actual Ollama Cloud Gemma vs local Qwen same-evidence capture (2026-11-04)

## What the user's run does and does not establish

The user supplied the official private-capture script's `baseline.json`
and `candidate.json` for a single frozen offline MQTT case.
The baseline is actual requested Ollama Cloud `gemma4:31b` and
the candidate is local Ollama `qwen3.5:4b`. This is
**not** an installed HomeBrainOS agent run; no live Hubitat or
Home Assistant tool calls, devices or rules were exercised.
The previously provided transcript includes only the trailing
`Most Useful Next Read-Only Check` paragraph, not enough to
recover or independently verify the whole Gemma first answer.
No Gemini, Claude, or OpenAI API call occurred in this comparison.

- Frozen case: `aq_network_broker_vs_device_health`; source
  packet SHA-256 `74ccff7fa2c23852655d12b45f6f5cbb6a3315de8c7647cac7b03441282f7150`.
- Source facts in the frozen fixture: broker session connected;
  endpoint genuine telemetry stale with offline healthStatus;
  watchdog writes `lastActivity` without new device payloads.
- Same recorded checkout SHA (not a production-deployment
  attestation): `0e71f92f380d21cfb2d3a17a66fbd40d85bd0684`.
- Each run record asserts `attempt_index=1`, not independently
  authenticated by the provider. The runner contract permits no retries.

| Arm | Provider | Requested model | Elapsed | Answer SHA-256 |
| --- | --- | --- | ---: | --- |
| Baseline | `ollama-cloud` | `gemma4:31b` | **828 ms** | `5a09a7146dd7351168426851c6edbecb8e42663557b2de38d2cf972fa88b38ad` |
| Candidate | `ollama-local` | `qwen3.5:4b` | **22,750 ms** | `2a1843c20024a7e83428a70de59d52dc5ef19f7a87beee341f73cf9bb7da60aa` |

Gemma Cloud's recorded first-answer latency was **21.922s lower**
than Qwen's, approximately **27.5× as fast** for this one
model-only request. This is not latency median/p95 or a
HomeBrainOS end-to-end performance number; network path,
warmth/caching, model settings, and provider execution
cannot be controlled from these manifests alone.

The Qwen candidate's SHA-256 **exactly matches** the earlier
user-shared local Qwen vs Llama frozen MQTT answer
(`2a1843c20024a7e83428a70de59d52dc5ef19f7a87beee341f73cf9bb7da60aa`)
whose reported local wall-time was **20,344 ms**.
This is consistent with byte-identical saved answer content
between these two local runs (subject to provenance of
user-shared hashes); time changed by +2,406 ms.
The cloud answer SHA differs from Qwen's.

## Model-quality limitation and requested completion

**Gemma first-answer source grounding, watchdog distinction,
causal calibration, usefulness and answer naturalness are
not scored.** The user provided only a fragment of the
Gemma answer in this turn, and no completed SHA-bound human
review file. The cloud first-answer output text must
be read from the user's existing private capture directory
and reviewed against the fixture before interpreting quality.
No qualitative model win is asserted from speed alone,
the shared trailing recommendation or the hash.

The supplied fragment recommends checking broker logs for
a session close/disconnect. That may be a useful network
discriminator but cannot alone prove which physical endpoint
failure occurred or establish if watchdog-written `lastActivity`
was mistaken for fresh telemetry; the full answer is needed
to determine whether these omissions occurred.

The benchmark tool's local Qwen arm may use top-level
`think:false` on models with supported off controls,
whereas the Ollama Cloud Gemma arm retains provider default
thinking behaviour. Both arms request fixed
temperature 0, seed 7, context 4096 and predict limit 320,
but implementation/effective inference settings and actual
provider ingestion are not independently verified.
This is **matched source packet**, not strictly identical
internal inference settings.

**Next:** Ask for the **two exact first-answer text files**
from the already complete private Cloud/local test, plus
the private `session.json` metadata if available.
No need to spend more Cloud allowance or repeat this MQTT
case. Privately perform a source-grounded review of both
outputs, then broaden to different frozen domains before
any production model-choice or publisher change.
The earlier local three-case `private transport or file error`
remains unresolved absent a new diagnostics-enabled
cross-domain run, and is not part of this valid Cloud pair.

**No new runtime changes** are justified here. Maintain
HomeBrainOS add-on v0.18.404, no device or Rule Machine
writes, and no assertion of Ollama Cloud cost/credit usage
(the manifest has no actual cost receipt).

## Full baseline answer received and independently hash-checked in conversation

**After the earlier metadata-only report**, the user pasted the *entire*
Gemma Cloud first response. Computing SHA-256 over exactly the pasted
UTF-8 text with LF line endings and **no trailing newline** yields
`5a09a7146dd7351168426851c6edbecb8e42663557b2de38d2cf972fa88b38ad`,
a byte-for-byte digest match to the user's saved `baseline.json`.
This authenticates consistency with the user-provided digest,
**not** independent provider/server provenance or execution mode.
The earlier isolated excerpt mentioning broker disconnect logs is
**not** the text of the matched Gemma answer: the hash-verified full
answer instead recommends reading the driver's `mqttStatus`
variable definition. Do not conflate those fragments or invent
a longer answer.

**Gemma's complete answer** records broker MQTT session connected,
device healthStatus offline, stale endpoint telemetry, and a
qualified explanation that `mqttStatus` may reflect the driver
broker connection rather than endpoint connectivity. It says
specific `mqttStatus` logic remains unknown and recommends
checking driver source code for its variable definition.
It does **not** mention the source-provided fact that a
driver watchdog writes `lastActivity` without a new endpoint
payload. It gives no verified physical root cause; the proposed
driver code check is a meaningful read-only way to verify
the `mqttStatus` computation, but may not distinguish the
watchdog-written timestamp from a real endpoint event.

**Same-packet Qwen response**, previously provided verbatim
and digest-matched between local comparison runs, correctly
covers broker/session versus endpoint health and explicitly
identifies the watchdog-written `lastActivity` as not being
a fresh device packet. It appropriately qualifies a physical
disconnection as only one possibility. It offers a broker
disconnect-log check rather than the more direct endpoint
payload versus watchdog `lastActivity` discriminator, and
some speculative background-process mechanism.

**Preliminary qualitative relative conclusion (not a blinded or
completed human rubric):** Gemma delivers a fast, clear,
source-consistent but **incomplete** first explanation; Qwen
offers **more complete coverage** of all three supplied
source facts with weaker efficiency. Neither asserts a
definitive unsupported physical failure. Neither should
be declared best overall on one MQTT case. The previously
measured 828ms versus 22,750ms requests are retained
unaltered; cloud cost is unverified. Full-source
reasoning quality has now been *qualitatively inspected*,
but no independent SHA-bound human scorecard form was
completed; **official human_reviewed_pairs and aggregate
model accuracy stay not_measured**.

**Next evidence, not a new output patch:** Complete the
previously blocked cross-domain command-attribution,
early-heating-off and Rule Machine native-identity cases.
For reliability, user may execute **one frozen local-only
case per new private directory** so a later failure
does not discard other cases' completed answers. The
existing runner does not save incomplete multi-case
results. Avoid new paid Cloud inference until the
case-level local process is stable and the user
explicitly authorises cost.
