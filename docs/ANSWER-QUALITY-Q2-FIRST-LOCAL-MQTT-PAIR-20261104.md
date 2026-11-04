# Q2 — actual local first-answer MQTT pair, preliminary evidence review (4 November 2026)

## Frozen experimental contract and observed first responses

The user successfully ran `scripts/answer_quality_q2_private_capture.py`
in a local Windows checkout after installing the merged answer-only
capture correction (PR #1415, documentation handoff #1416).
Both arms received the existing curated synthetic/anonymised offline
`aq_network_broker_vs_device_health` source packet through the
user-executed Ollama-local capture tool; the tool saved two **raw
original model texts** privately. No HomeBrain publisher was used.
The command was local-only, with no Hubitat/HA read, no MCP tools, no
cloud provider arm, and no automated retry.

Frozen source packet SHA-256:
`74ccff7fa2c23852655d12b45f6f5cbb6a3315de8c7647cac7b03441282f7150`

The three source facts are: driver's MQTT session remains connected;
endpoint genuine telemetry is stale and Hubitat health reports offline;
driver watchdog writes `lastActivity` without endpoint payloads.
Reviewer obligations are separate from the model prompt.

| Arm | Model | Provider | Recorded wall latency | Original answer SHA-256 |
| --- | --- | --- | ---: | --- |
| Baseline | `qwen3.5:4b` | `ollama-local` | **20.344s** | `2a1843c20024a7e83428a70de59d52dc5ef19f7a87beee341f73cf9bb7da60aa` |
| Candidate | `llama3.2:3b` | `ollama-local` | **8.531s** | `e0cdb67452889dae74caa65122ba28907a605b56db245fb7060f54de163d6184` |

Same user-reported checkout `build_sha` on both arms:
`0e71f92f380d21cfb2d3a17a66fbd40d85bd0684`.
Both metadata manifests have `attempt_index=1` in this **new** run.
The earlier unsuccessful pre-fix run did not yield a complete pair and
must not be retrospectively scored. Requested benchmark settings:
temperature 0, seed 7, context 4096, prediction limit 320.
The capture tool's current local policy requests `think:false`
where supported by model metadata. Provider compliance, exact
content ingestion and independently verified first-attempt status
were not attested by these manifests. The `build_sha` is
checkout metadata, not independently verified runtime deployment.

Llama was **11.813s faster (58.1% less recorded wall time)** than
Qwen on this one paired offline first-answer capture. The timings
are model-only local request measurements, not production HomeBrain
latency, a p95, or a statistically robust speed ranking. No cloud
API charges are associated with this local-only test by the
declared provider configuration; actual machine operating cost
was not measured.

## Preliminary source-based qualitative assessment — NOT official scorecard

The raw model answers were shared in the user conversation and
reviewed *qualitatively* against the versioned fixture. No
independently authenticated human/blinded rubric manifest was
supplied, so the official `human_reviewed_pairs` and semantic
quality scores **remain not_measured**. Do not generate or fill
fictitious human review scores, review attestations or grades.

- **Qwen3.5 4B:** Separates broker/session connectivity from
  stale endpoint telemetry, accurately notes the watchdog
  writes `lastActivity` without endpoint payloads, and
  correctly presents possible physical disconnection as a
  *hypothesis*, not a proven network/power cause. Its
  suggestion that background processes explain watchdog
  behaviour is speculative, though qualified; the provided
  source already states that the watchdog writes the field,
  not how the internal mechanism works. It offers a useful
  broker-log next check, but comparison of last genuine
  endpoint telemetry with watchdog-written `lastActivity`
  would discriminate data freshness more directly.
  The answer is structured and somewhat longer than necessary.
- **Llama 3.2 3B:** Gives a concise distinction between
  a connected MQTT session and stale/offline endpoint
  telemetry, without definitive network/power attribution.
  However, it omits the available watchdog `lastActivity`
  fact and does not provide a read-only next discriminator.
  Its assertion that the driver is not receiving updates
  should be read as an inference from stale telemetry,
  not independently proven full absence of packets.
- **Relative qualitative outcome on this single case:**
  Qwen covers more of the frozen evidence; Llama is
  meaningfully faster and more concise, but less complete.
  Neither demonstrates broad model superiority. The input
  question's word “disconnected” is not independently
  verified physical reachability; do not promote it to proof.

No lexical keyword rubric or model-authored narrative is an
automatic truth score. Human source review (or another
explicitly disclosed non-human review category) must preserve
the distinction between provider execution, model answer,
evidence truth and any HomeBrain post-publication repair.

## Next Q2 phase (do not repeat this exact MQTT case)

One pair is not enough to choose a model or simplify the
publisher. Next, run the **other three** frozen original
cases on the same two locally installed models in a *new*
private output directory:
`aq_command_issuer_vs_reporter`,
`aq_early_heating_off_resume`,
`aq_rule_parent_type_gap`.
Retain the same model ordering and requested settings.
The new cases test command/report attribution, heating
setpoint/demand, and missing native Rule Machine identity.
No user household information or real Hubitat rules are
part of these synthetic source packets.

After genuinely reviewing the *actual* answers and preserving
the answer hashes privately, use the existing answer-SHA-bound
paired-review CLI. Until complete, formal factual grounding,
first-answer usefulness, Claude/Gemma quality and privacy/
cost-normalised performance scores remain **not_measured**.
No code patch, runtime version update or model-routing switch
is justified by this individual result.
