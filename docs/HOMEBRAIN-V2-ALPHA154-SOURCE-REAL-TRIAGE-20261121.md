# Alpha.154 installed redacted report — ungraded source triage

**21 November 2026.** Observations from the owner-supplied redacted capture report only. No raw first-answer exports were available for this review. Original alpha154 and all earlier cohorts remain unchanged.

## Source and provenance

- Report schema: homebrain-v2-source-real-acceptance-report.v1.
- Frozen pack: alpha154-prospective-v1. Version: 2.0.0-alpha.154.
- Manifest SHA-256: 6eb8cc086bfa28e82281166a031b3ce47ca5eecfeda3d894139003a583ff3ac7.
- All ten cases a154-01 through a154-10 captured in order; no missing cases, version mismatches, reported prior-chat evidence or attempted device commands.
- Model fingerprint consistent. Package provenance bundled_manifest_no_build_arg is permitted, but does not independently establish build integrity.
- Report fields say original source, first-attempt provenance and read-only permission *independent verification* are all false.
- Ten original source-reported hub_get_info permission preflights indicate per-client **Read ON / Write OFF**; global writes are enabled. Global permissions cannot substitute for the client's grant, and these fields are not an independent enforcement test.

## Mechanical results (NOT quality scores)

There were **21 attempted and 21 successful native calls**, no tool attempt failures, and one unsuccessful first answer (a154-03). Median reported **server** elapsed is 18.230 seconds, maximum 38.644 seconds (a154-02). Browser elapsed and source-graded answer accuracy remain unknown.

| Case | Redacted report observation | Needed original-source check |
| --- | --- | --- |
| a154-03 | First answer failed; both tool calls succeeded | Inspect response error/finalizer and full first-answer receipts, without inferring cause |
| a154-04, a154-05, a154-07, a154-08 | Device event row limit reached | Check request window, returned dated observations, continuity and absence claims |
| a154-06 | Past-log row limit, reported matches exceed returned rows | Check requested mode, original nested/direct log envelope, counts and prose |
| a154-10 | One log receipt reports more matches than returned rows | Inspect matching semantics and any historical-absence claims |
| a154-02 | Longest server time, 38.644 s | Inspect actual detailed/summary inventory requests and response shapes before attributing latency |

No complete history coverage is established. A limit hit is not itself a bad answer; a native call success is not semantic correctness. Command issuer, state reporter, notified listener, installed app configuration, actual execution decision, stored lastActivity, and dated physical measurement must be kept separate.

## New independent offline tool

From the repository root:

    python hubitat-mcp-ai-v2/tools/acceptance_report_triage.py /private/capture-report.json --output /private/triage.json

The helper is report-only, no network/model/native calls. It produces a priority list with explicit **unscored / promotion_ready=false** and never includes private labels, questions, answers, argument payloads or logs. Synthetic tests cover structural failures, privacy, permission distinction and review order. This is a reproducible observation aid, NOT a human grade or automatic source attestation.

## Before selecting a new runtime repair

1. Export all **ten original per-case first-answer JSON files**, and preserve their sealed manifest and redacted report separately. Never rerun or alter cases.
2. Independently attest original source and first-attempt integrity; check the actual dedicated per-client Read ON / Write OFF grant and separately test enforcement.
3. Human-score each first answer against its original source receipts, including failed a154-03. Quantify atomic factual claims, group coverage, useful/complete responses and unsupported definite causes.
4. Apply original promotion gates: at least **90% atomic factual grounding**, **80% useful complete**, zero unsupported definite causes, zero write/approval regression. Missing quality scores are not passes.
5. Only then design a general code repair from verified source-specific failure modes, with cross-domain regressions and fresh, distinct prospective evidence. Do not pool earlier alpha151/152/153 cohorts.

**Safety scope:** documentation and offline triage only. No installed runtime, V1, heating scheduler, native write/approval, MCP source choice, model/provider or capture change.
