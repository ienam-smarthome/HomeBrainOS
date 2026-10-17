# 0.18.13 — Reconcile source-workbench proof across evidence paths

## Live observation
Installed 0.18.12 completed a read-only Groovy investigation for app 4019, code ID 1453: four verified workbench pages covering 186,457 of 186,457 reported source-offset units and a useful explanation. However, the final API simultaneously reported `fullImplementationVerified: true` and `chunkCoverage: {fullImplementationVerified: false, chunksObserved: 1, coverage: partial}`. An earlier 10,000-unit direct source probe prevented the existing final assessment from showing the later complete workbench proof.

## Correction
- Reconcile direct gateway source spans and local workbench coverage as distinct, independently checked sources. Choose a complete workbench result for the primary `chunkCoverage` when a direct probe is partial; keep the partial direct observation under `directChunkCoverage`.
- If direct spans are complete and workbench evidence partial, retain direct coverage and expose partial `workbenchChunkCoverage`.
- Treat inconsistent workbench complete flags, verified offset totals or zero pages as unverified rather than upgrading a partial read to full.
- Distinguish full-file retrieval from method-body, call-graph and runtime proof in `methodBodyCoverage` and the coverage completion note; do not claim every requested code path has been reviewed based only on successful page retrieval.
- Reinforce model-led source tool guidance: the workbench `appId` means the installed instance ID, never the distinct verified underlying code ID. Applies generically to any app, with no named-app repair.
- Regress the live evidence shape (failed first app-ID probe, partial 10k direct read, complete four-page workbench), the inverse case (complete direct reads with partial workbench), and inconsistent declared counts.

## Scope and safety
Read-only final evidence classification, source-tool guidance and tests only. The tool model remains responsible for source interpretation; no auto-change of Hubitat devices, source code, rules or Ollama paid-model budgets. No remote Hubitat state changed by this release.

## Validation
GitHub CI release gates required before merge. Runtime behaviour on the Home Assistant add-on must be verified after installing 0.18.13.
