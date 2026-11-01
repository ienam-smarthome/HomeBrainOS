# v0.18.336 — source-scoped admission of model-directed broad device reads

## Evidence and hypothesis
Real read-only v0.18.335 HomeBrain investigation of one named device reported 24.910 s elapsed, 5 Ollama Cloud Gemma rounds and 8 tool calls. Targeted live attributes, an ID-scoped 24h history (11 health reports, 0 commands), device logs and configuration were followed by a whole-hub `hubitat://context` read of 207 records and a name filter for unrelated device family. These latter reads did not corroborate endpoint liveness or explain offline status. The publisher returned a concise, cautious **source-generated** explanation; `modelProseCertified=false` and `replacementPerformed=true`. No raw model draft had been source-attested. A previous v0.18.333 11-round/approximately 42s trace is **not** a matched source-window latency A/B.

## Runtime change
- New `single_device_read_scope.py` establishes a strict identity gate: `device_telemetry` domain, precisely named device in the original question, single ID-scoped mixed event-history receipt and matching targeted reported-device-state receipt. It fails open if any part is missing, if the investigation covers multiple devices or if the user explicitly requests comparisons/whole-home inventory.
- Once gated, reject *late broad reads only*: whole-home `hubitat://context`, local whole-home snapshot, unscoped `hub_list_devices` and unrelated `homebrain_filter_devices` **name** filters. Return one source-safe skip note pointing to already verified target evidence and relevant next read-only diagnostics.
- **Keep allowed**: target and related-device scoped gateway reads, native device/app logs, driver source, broker/network diagnostics, multi-device comparisons and all unrelated domains (lighting, heating, control). No new model call, no new MCP read and no write privileges.
- Record a bounded `single_device_broad_reads_suppressed` counter without target identities or raw request text. No invalid inference that a skipped read proves a source absent.

## Quality and limits
Unit cases validate target ID, targeted state, label match, single-source scope, controls on unrelated filters, allowed source-linked tools, intentional comparison requests, ambiguous/multi-target failures and cross-domain negative controls. Full existing Python, add-on smoke, release and offline-scorecard checks must be green on exact PR head.

This change **can reduce unnecessary broad calls**, but an extra model retry may offset savings; actual rounds, latency and clarity of v0.18.336 **NOT MEASURED** until a new read-only live trace. The official scorecard remains **NOT MEASURED**. It does not fix the missing raw-model-draft attestation or independently prove a plug's physical cause. Next Q3 milestone: instrument verifiable draft-to-publication identity and source-backed claim admission; do not enable unrestricted model publication from generic validator success.

## Rollback
Revert the new policy function's orchestrator call and module. Existing broader read behavior returns without changes to source/publication contracts.
