# Hubitat MCP AI v0.18.274 — Stage 2.5 offline shadow comparison

**Not an installed or activated release.** This source version exists to satisfy
the runtime-module versioning gate for the separate stacked shadow PR.

- Adds `shadow_evidence_comparison.py`, a bounded, offline comparison between
  canonical source receipts and the existing V3 witness ledger.
- Flags missing scoped device names, command-issuer name loss, mismatched
  journal query gap counts, and unmatched timestamp-qualified witness rows.
- Keeps source clocks distinct from collector reception, and never equates a
  correlated sensor or event listener with a proven command issuer.
- Adds anonymised five-cycle, HVAC command, loss/truncation, no-writes and
  compute-only performance regression tests.
- Does **not** change active model prompts, routing, planner, final publisher,
  tool calls, HA integration or Hubitat controls.

This is stacked on foundation PR #1160 (v0.18.273). Merge foundation first,
then review/rebase this change and rerun CI before any code lands in main.
No live upgrade is requested. Documentation:
`docs/INVESTIGATION-STAGE-2P5-SHADOW-COMPARISON.md`.

Rollback: close/revert this additive PR. No database, config or live changes.
