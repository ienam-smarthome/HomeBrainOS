# HomeBrainOS v2 alpha.27 — prospective source-real A/B (private, opt-in)

**Milestone:** opt-in evaluation capability; the first two real-source A/B pilot pairs are now complete and manually scored, but candidate promotion is not justified. The ten original sr-series cases, six earlier fictional holdouts and two new-series pilot cases are exposed and cannot serve as future unseen validation.

## Evaluation update — 10 November 2026

The first two genuine source-real A/B pairs are now complete and scored. **The experimental source ledger has not been promoted:** it scored lower on factual grounding and source completeness, higher on usefulness, and causal calibration was not tested. This small pilot does not establish a general effect. The exact scores, limits, and next unseen evaluation gate are in [source-ledger pilot results](HUBITAT-MCP-AI-V2-SOURCE-LEDGER-PILOT-RESULTS.md). The previously frozen pair questions are now exposed and should not be reused as new validation. The Real-source A/B tab remains opt-in; ordinary Ask behavior is unchanged.

## What changes

The new Real-source A/B tab compares the unchanged production Agent (existing event-source scope notes) against the isolated SourceLedgerExperimentalAgent (source-derived inventory, attribute and log-page coverage ledger). Both use the same configured model and live read-only MCP catalog, selecting tools independently and answering naturally. Ordinary Ask/Chat always uses the unchanged production Agent. Source snapshots can drift between sequential live reads; independent reviewers must flag any unequal evidence before drawing causal conclusions.

## Safety and permissions

1. On Hubitat: Apps > MCP Rule Server > Settings > Advanced > Per-client access tokens. For the dedicated evaluation client, set **Read ON / Write OFF**. Global Write may stay on for other clients.
2. In Home Assistant v2 add-on Configuration, replace the MCP URL/token with that dedicated client's access. If the URL contains access_token=, replacing only the separate token field will not override it. Restart v2. Never publish tokens or URLs.
3. In Real-source A/B click Check client access. The feature makes a **read-only** hub_get_info call. Its **clientAccess** must report readEnabled=true and writeEnabled=false. A top-level global writeEnabled=true alone is not proof of token access.
4. The runner repeats that client grant check immediately before EACH model arm. The experimental model tool surface only includes tools whose upstream annotations explicitly say readOnlyHint=true; a selected gateway leaf must itself be annotated read-only. Unknown or conflicting classifications fail closed. Upstream server token enforcement remains authoritative. No write-test command is executed.

## First new pair

1. Verify the exact target identity and capability directly in Hubitat before drafting questions, avoiding earlier mistaken app/device targets.
2. Enter two to ten **genuinely new** read-only investigation questions, one per line. Freeze once. The application stores an in-memory SHA-256 commitment and private question bank; no raw data enters the repository.
3. Select new-01, acknowledge model/evidence consent and (for cloud/remote models) cloud transfer and possible cost. Click Run blinded read-only pair.
4. Two model-led first answers run sequentially with independent fresh context, identical permission-scoped tool lists and one source-ledger difference. The run is user-triggered and may consume configured cloud model credits; it does not initiate device control.
5. Review both answers and native tool receipts. Download PRIVATE case JSON to a secure local folder. The case file contains household questions, model answers and source payloads; do not publish it.
6. Rate A/B independently on factual grounding, source completeness, causal calibration and usefulness (0 unsupported, 1 partial, 2 supported, n/a genuinely inapplicable). All ratings are immutable, and first answers cannot be rerun. Identify source-state drift and insufficient target validation separately from model failure.
7. Repeat for the frozen set. Mapping stays hidden until ALL cases are rated. Download only the privacy-safe aggregate report for repository development notes.

## Limitations

- Installing or opening this tab makes **no** cloud/model or Hubitat calls; the optional permission check reads hub info only. Only explicit paired Run starts two sets of model requests with live read-only MCP sources.
- The private experiment is **in-memory only** and is erased by add-on restart or explicit deletion. Save PRIVATE case exports first.
- A reported clientAccess read-only grant is a server report, not an independent penetration test. The model answers and tool receipts may contain sensitive household data despite the write restriction.
- Reviewers see the original MCP source payload with the candidate annotation marker removed to protect blinded allocation; the natural answer may still reveal the method. Reviewer blindness and source truth remain not independently verified.
- This is a test of general evidence aggregation, not an incident-specific prompt or hard-coded source plan. Structural CI does not establish measured AI answer improvement. The experimental candidate remains **unpromoted**; do not use old holdouts or sr-series cases as fresh validation.
- The opt-in UI is included in add-on **2.0.0-alpha.27**; repository updates alone do not install it. Normal Ask, v1, Hub Diagnostics and existing MCP access controls remain unchanged.
