# HomeBrainOS v0.18.176 — Golden Evidence Plane (Phase 0 / 1 foundation)

## Why this release

The direct-read causal investigation of Livingroom Light 2 (Hubitat device
7828) initially failed to retrieve command-off because an attribute=switch
history query excludes separately named command events. v0.18.175 introduced
an unfiltered follow-up read. However, the AI architecture still needs
a general source-evidence contract and reproducible quality gates instead
of a succession of wording-specific fixes.

## Implemented

1. New general investigation_v2/causal_evidence.py:
   - One-to-one source-time command-on/off -> same-target reported switch
     association within a configurable 0..60s window (default 2s).
   - Explicit separate command issuer app ID and state reporter ID; no
     upgrade of temporal proximity to physical actuation or rule execution.
   - Explicit warnings when command history was filtered to switch and no
     unfiltered sample was retrieved; missing command records never assert
     that no commands occurred.
   - A bounded machine-readable causal evidence bundle for the verified ID.
2. Planning evidence now contains source-linked command/state pairs and
   command-history coverage flags, provider-independently. The existing
   case file, source receipts and host read-only gates remain authoritative.
3. Reproducible offline golden harness:
   - tests/fixtures/investigation_v2_light2_2026_10_28_golden.json
     transcribes user-supplied Claude event observations with explicit
     provenance; it is NOT independently captured live Hubitat evidence.
   - Required evidence fixture includes command-off #4020 at
     2026-10-28 00:14:56.868 UTC followed by switch=off from Matter bridge
     #7790 at 00:14:57.111 UTC (243 ms).
   - Reference-only sensor, rule config, log/restart and alternatives
     are explicitly not promoted into verified canonical source records.
   - The suite detects that switch-only filtered history is command-incomplete;
     catches wrong device, reversed clock, incorrect command and wrong issuer.
   - scripts/run_v2_golden_suite.py is an explicit read-only, no-network,
     no-model release assurance gate with machine-readable results.
4. Multi-domain golden task catalogue and phased shared-agent architecture:
   - tests/fixtures/homebrain_golden_tasks_v1.json
   - docs/HOMEBRAIN-UNIFIED-AGENT-MIGRATION.md
   - Existing Main Ask control and all confirmation/backup/write
     protections are unchanged.

## Strict scope and next milestones

This is a **structural replay contract**, not a final Claude-equivalent
semantic benchmark. There is no automatic sensor/config/restart fetch in
this release, no production write migration, no native tool-call switch,
and no evidence journal setting change. The fixture is a sanitised
transcription, not historical truth independently certified by this code.

Next slices should capture actual redacted MCP receipts, implement general
source-verified controller/sensor/restart playbooks, then introduce native
tool calling through live schema-projected subtools and host safety
middleware. Keep V2 read-only and V1 production writes stable until
equivalence and sensitive-write tests pass.
