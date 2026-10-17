# 0.18.11 — Groovy method-scope evidence, combining HomeBrain development threads

## Baseline
The two active HomeBrain investigations are reconciled: v0.17.91 introduced route-aware health/performance audit coverage and stronger source-claim boundaries, while v0.18.8–0.18.10 added verified installed-app-to-code mapping, source workbench, page continuation, safe gateway normalisation and adaptive recovery from a one-character `nextOffset` mismatch. PR #889 is merged. Neither thread needs to be reverted or replayed.

## Remaining live problem
The 186,457-character Groovy implementation (code ID 1453) can be recovered in principle, but a **fully retrieved file is not a complete explanation**. The existing workbench scans symbols and returns ~31-line neighbourhoods with a finite shared excerpt budget. For long Groovy methods, the end of `updated()`, `initialize()`, a runtime getter, or the last modification of stored expiry state could be omitted even when the full raw source was downloaded.

## Improvement
- New generic lexical method-scope index locates typed or `def` Groovy signatures and source-relative balanced candidate bodies, ignoring quoted strings and ordinary line/block comments.
- Model-selected symbols get fair per-method scopes, not a canned investigation into app 4019. Full candidate method bodies are supplied when budget permits; omitted, oversized, incomplete, and uncertain lexical scopes are labelled explicitly.
- Existing symbol-neighbourhood excerpts remain, using the remaining response budget. A full-source report still independently requires successful contiguous source-character reads and consistent identity/length/version.
- Groovy slashy-string literals and incomplete braces are **not** certified as structurally complete. An included method excerpt is source evidence, not a compiler-verified call graph or proof of every caller, state mutation, persisted value, or runtime behaviour.
- Bounded existing 250k char / 32-call retrieval limits, read-only permissions, safe gateway normalization, model autonomy, Ollama paid-model budgets, and all MCP tool restrictions remain unchanged.

## Verification
Tests cover quoted/commented braces, nested Groovy blocks, selected field read/write owners, oversize-method omission, uncertain regex boundaries, no-name-found behavior, and full 186,457-character / four-read model-selected method investigation, in addition to the full existing repository gates.

## Release-gate reliability improvements
- The mandatory Python release gate now includes both `tests/` and `hubitat-mcp-ai/tests/`. Previously the second tree's source-workbench and historical-evidence regression cases could be omitted despite all workflows appearing green.
- Enabling these checks exposed historical whole-date versus focal-time command-denial bugs and a cross-date evidence summary with malformed wording; the corrections preserve supported command dates while refusing to infer the exact missing state transition.
- Corrected a double-escaped regular expression in the targeted automation-history classifier. A single app/rule history request now stays out of the general all-automations inventory route.
- Updated old source-workbench test doubles for the new model-selected symbol parameter, and retained conservative lower-cost paid-model routing for a non-causal history analysis.

## Next priorities
1. Live verification on installed 0.18.11 and provider availability using Gemma first.
2. General hypothesis evaluation and source-value ranking across both source-code and device-history investigations; do not hardcode the answer to motionOffLockoutMinutes.
3. Separately assess the previously measured ~27s audit inventory and ~18.9s performance read; neither establishes a CPU fault.
