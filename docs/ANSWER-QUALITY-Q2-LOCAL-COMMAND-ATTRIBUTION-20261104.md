# Q2 — actual local OFF command issuer vs Hue state reporter (4 November 2026)

## Verified original first-answer pair, frozen evidence

The user successfully ran the private Q2 local-only benchmark on
`aq_command_issuer_vs_reporter` with one requested answer per model.
This is a synthetic/anonymised offline evidence packet; no Hubitat/HA
tools, real devices, cloud calls or rule writes were used.

The immutable source packet `fbe2452406077b244438396d54a73636d43b0f1d30212597c97c54c9798ba0ea` contains **only**:

1. At **15:29:23.157 UTC**, a *recorded command-off* is
   attributed to **app 4012**.
2. At **15:29:24.367 UTC**, a Hue-bridge-provided switch
   OFF *state report* was recorded (1.210 seconds later).
3. The OFF state report lists **app 4012 as a notified
   listener**, not the producer of the report.

The contractual source claims are: app 4012 is the recorded
command issuer, Hue bridge is the state reporter, and neither
the historical internal app trigger nor actual physical
actuation/command delivery is independently established.

Both saved raw answer texts were pasted in conversation.
Computing SHA-256 over exactly the pasted UTF-8 texts with LF
line endings and no trailing newline independently reproduced
both manifest digests:

| Arm | Model/provider | First attempt | Time | Exact saved answer SHA-256 |
| --- | --- | --- | ---: | --- |
| Baseline | `qwen3.5:4b` / `ollama-local` | 1 | **26.344s** | `a5479755e6b750941a1a283d00bdcc0ee1f90e31600f2c9e1008a239327fc064` |
| Candidate | `llama3.2:3b` / `ollama-local` | 1 | **10.594s** | `fe3bdf3ce62350edf2d00de3d51ae501a26b0b84e612ce81a439807369a305c2` |

Both manifests report local checkout build SHA
`25a09d0ed5cd3f0bfdd2aac20147f50a0d719c29`
and the same source packet SHA. These are user-supplied
manifest values (not independently attested model
ingestion or live HomeBrain deployment).
Llama's measured local response was **15.750s shorter**,
approximately **59.8% less wall-time** on one case.
These are model-only first-call times, not production
end-to-end or a latency distribution.

## Preliminary source-based answer inspection (NOT human scorecard)

**Qwen3.5:4b:** Correctly attributes the recorded OFF command to
app 4012, the following state report to the Hue bridge, and
distinguishes a notified listener from report producer.
But it says the bridge confirmed the state change
`based on the received command`, which **overclaims
command receipt, causal execution and bridge observation**.
It also invents a possible third-party subscription
mechanism not available in the packet.
Its saved original answer **ends in the middle of the
heading** `**Most Useful Next Read`. This was independently
verified by matching the exact pasted truncated text to
the recorded answer digest. The provided response is not
a complete coherent answer, despite the runner's old
acceptance of `done:true`.

**Llama3.2:3b:** Identifies the report producer and
app 4012 as a listener of the report, but falsely
infers the device **received** the OFF command,
**was already OFF when it arrived**, and therefore
app 4012 **did not initiate** the OFF. This last claim
contradicts the separate command record attributing
the issued command to app 4012. It makes an unsupported
physical/temporal attribution from two historical
records and conflates report listeners with command
issuers. It has lower latency and a more concise
text, but is not causally grounded.

**Both require improvement.** Do not count these
as safe/fully useful first answers. This is a
qualitative source comparison from conversation,
**not** a blinded independent human attestation,
completed answer-hash-bound rubric, official accuracy
score or a reason to switch production models.
Neither model's unsupported assertions should be
repaired with a literal phrase/room-specific patch.

## General Q2 first-answer completeness defect and correction

The saved Qwen output demonstrably ends mid-heading.
The private runner previously checked only
`done=true` and presence of nonempty `message.content`,
without considering Ollama's `done_reason`. Ollama
upstream API `llm/server.go` uses `done_reason=length`
when a generation is stopped at its token limit,
and `stop` for normal completion. Docs:
<https://github.com/ollama/ollama/blob/main/llm/server.go>;
<https://github.com/ollama/ollama/blob/main/docs/openapi.yaml>.

This is a **plausible** cause of Qwen's truncated
320-token output, but the original capture
**did not save the provider's done_reason**.
The actual historical stop reason must remain
unverified; do not retrospectively classify it
as proven `length`.

The local and Cloud benchmark transport now
fail closed on an **explicit** `done_reason=length`
even with `done=true`, and refuse unexpected
stop reasons. A normal `stop` remains accepted,
while an absent optional done_reason remains
backward-compatible. Never silently retry,
increase `num_predict`, or represent a truncated
output as a complete first answer in a new capture.
A missing reason does **not** establish
model response completeness.

Regression tests use fake Ollama envelopes for
both providers; they do not execute AI models.
No new A/B first-answer evidence is generated
by a unit test or GitHub CI. Existing source
packets, default `num_predict=320`, privacy,
cloud acknowledgement, model thinking policy and
HomeBrain add-on v0.18.404 are unchanged.

## Next source-backed evaluation

Continue with the unrelated **early-heating-off**
case (`aq_early_heating_off_resume`) as one
local-only Qwen vs Llama pair in a new external
private directory after CI and merge. Review
whether the models separate temporary setpoint
override from physical boiler firing.
Then test `aq_rule_parent_type_gap`, where a
native Rule Machine parent label must not be
mistaken for source-typed identity.

No production change or new Cloud charge
is required. If a provider explicitly reaches
the 320-token limit, record the failure, do not
retry it automatically, and design a new
transparent, separately labelled experiment
before changing the capture token budget.
