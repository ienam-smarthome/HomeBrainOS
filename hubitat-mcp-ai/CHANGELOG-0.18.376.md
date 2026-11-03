# 0.18.376 — Q3 evaluate telemetry sufficiency after completed read rounds

## Source-real first answer and baseline

The registered read-only `device_mqtt_conflict` question was run on installed HomeBrainOS **v0.18.375**, with **Gemma4:31b / ollama-cloud**:

- **39.649 seconds elapsed**, 37.920 seconds agent phase, **34.027 seconds provider**; 8 provider model rounds, 7 read-tool calls, 0 paid rounds; original evidence and tool read receipt timestamps supplied by the user, no live device changes.
- Published first answer was concise and properly separated `healthStatus=offline`, `mqttStatus=connected`, physical packet freshness and unknown root cause. `answerPublicationDecision.mode=concise`, `replacementPerformed=true`, `rootCauseVerified=false`, `questionResolved=false`; causal calibration **PASS** on this one source-reviewed attempt.
- The model's original draft was **not published**; `modelFirstRejection=material-uncertainty-omitted`. This is evidence of a guarded publication, not proof that the model independently reasoned to a grounded answer.
- This history has **16 reported / 16 retained and `truncated=false`**. Its concise mode does NOT test the new v0.18.375 specifically counted-partial publication path.
- `telemetry_sufficiency_stop` absent, `causal_read_round_budget_exhausted=1`, two `investigation_source_checkpoint_offered`, a successful target-scoped log read and a later config read. The exact model's internal source choices were not captured; the observed source packets and code motivate a generic latency hypothesis but cannot alone prove how many rounds are avoidable.

## Implementation

The existing `ready_for_bounded_telemetry_answer` checked a source-sufficient single-target diagnosis **only when a model gave a no-tool response**. A final successful targeted read could satisfy its exact status/history/log plus discriminator/checkpoint obligations without another model round, but the outer loop did not check that opportunity until the next no-tool turn or after budget exhaustion. New code invokes the **same, unchanged source-sufficiency contract** after a successful nonmutating tool round with at least one newly recorded successful read receipt. A round with duplicate-only calls, failed tools, write requests, no new read or unsuitable investigation scope does not qualify. It passes through the existing final no-tools synthesis, host source completion and source-safe publication; it does not infer physical state or cause from a successful query.

This changes model-loop scheduling only. No MCP call, provider call, confirmed action, live device, permission, command or configuration is changed. It is independent of actual device label, room, MQTT product and integration.

## Evaluation / safety / rollback

**Observed live before v0.18.376:** v0.18.375 = 8 rounds / 7 tools / 39.649s; user-facing cause calibrated, real physical explanation unresolved. Earlier same-question runs: v0.18.373 = 57.559s/8 rounds/9 tools/unsafe causal assertion; v0.18.374 = 44.647s/8 rounds/8 tools/grounded but verbose. Conditions and source histories differ; do NOT treat downward elapsed sequence as a paired benchmark or assign model-wide accuracy percentages.

**Offline acceptance after:** Tests require post-read readiness only after new successful read and previously verified same-target status/history/scoped log/discriminator/checkpoint, reject failed/duplicate/mutating/wrong-target/other-domain cases, and preserve v0.18.375 counted-partial and detailed-publisher tests. Full CI suite required before merge.

**Real v0.18.376 after:** NOT MEASURED. Hypothesis predicts fewer avoidable tool-planning rounds, not guaranteed lower wall-time or increased correct diagnoses; source-read order could make the new gate unreachable. This is not a Gemma-vs-alternative model A/B, and the model-authored draft still requires causal/provenance validation. Next permanent milestone: reproducible same-evidence model comparison / first-response review across different domains, not another endless MQTT-specific release.

**Risk:** Premature finalization after a qualified source read might forgo another useful tool request; the existing bounded telemetry readiness, verified scope and source category requirements are unchanged, and final source completion still runs. Full user-requested multi-device comparisons, lighting/heating causal histories, writes, speculative or mismatched receipts must not become early source-sufficient. **Rollback:** revert the post-read telemetry helper, its orchestrator call and release metadata; no live hub rollback required.
