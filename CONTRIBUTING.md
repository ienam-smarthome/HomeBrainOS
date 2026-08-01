# Contributing to HomeBrainOS

## Change existing modules before creating variants

A bug fix belongs in the existing live implementation. Do not create files named with suffixes such as `_final`, `_safe`, `_verified`, `_fixed`, `_v2`, `_new` or `_release` unless the file represents a genuinely separate capability with its own public contract.

Before adding a new Python module under `hubitat-mcp-ai/rootfs/app`:

1. Check `docs/ARCHITECTURE.md`.
2. Run `python scripts/analyze_imports.py`.
3. Confirm that the capability does not already exist in a live module family.
4. Prefer configuration, composition or a focused edit over another wrapper/subclass generation.
5. Add regression coverage for the behaviour being changed.

The cluster analyzer treats ordinary same-family function composition as live,
but flags unlisted sibling-only inheritance as suspect. An intentional
inheritance layer must be documented, tested and narrowly allowlisted.

## Safe consolidation

Do not delete a same-family module merely because its name looks obsolete. Many current modules are load-bearing inheritance or wrapper layers. Flatten one family at a time:

1. identify the directly wired entry;
2. map inherited/imported behaviour;
3. port required safety checks;
4. add tests;
5. switch imports;
6. verify no importers remain;
7. delete the old file.

## Validation

At minimum, run:

```powershell
.\.venv\Scripts\python.exe -m py_compile <changed Python files>
.\.venv\Scripts\python.exe scripts\validate_addon.py
.\.venv\Scripts\python.exe -m pytest -q <focused tests>
git diff --check
```

For release or routing changes, also run `scripts/run_release_gate.py` when the local environment has all test dependencies installed.

## Release metadata

Keep the Hubitat MCP AI version aligned in:

- `hubitat-mcp-ai/config.yaml`
- `README.md`
- `hubitat-mcp-ai/README.md`
- `hubitat-mcp-ai/CHANGELOG-<version>.md`

Do not claim CI or tests passed without actual results.

- Do not use query keywords or regex intent classes to gate read versus mutation behaviour; gate the actual requested tool call using tool metadata.
- Classify tool effects from the declared tool and structured call arguments;
  never infer a tool effect from raw user-prompt wording.
- Do not select remote MCP schemas from prompt keywords or regex categories.
  Keep the initial registry bounded and use structured `hub_search_tools`
  results to expand it.
- Preserve bounded conversation and cumulative tool-result budgets in both
  streaming and non-streaming Ollama requests. Never compact the authoritative
  evidence receipts or mutate the in-process transcript while preparing a
  model payload.
- Keep provider HTTP and streaming mechanics in `chat_transport.py`. Transport
  code must not classify requests, execute Hubitat tools, or decide mutation
  confirmation policy.
- Keep pending confirmation lifecycle in `confirmation_store.py`. Keep
  stateless confirmation eligibility, group limits, session validation, and
  deterministic confirmation wording in `confirmation_policy.py`. Tool-effect
  classification stays in `tool_registry.py`; action execution stays outside
  both confirmation modules.
- Keep evidence receipt construction, nested argument redaction, and
  request-context storage in `evidence_recorder.py`. Keep authority decisions
  outside it: callers must explicitly decide whether a result supports a live
  claim.
- Keep bounded evidence/log retry state and deterministic refusal wording in
  `grounding_policy.py`. The policy may consume resolved booleans and executed
  tool outcomes, but it must not inspect prompt text, execute tools, mark
  receipts authoritative, or own successful-answer presentation.
- Keep approved structured-call dispatch, timing, success normalisation,
  receipt emission, and bounded model-result serialization in
  `tool_executor.py`. Tool visibility, confirmation, live-claim authority,
  retries, and user-facing presentation remain orchestrator policy.
- Keep initial registry ordering, declared/available state, schema rendering,
  and structured search-result expansion in `tool_discovery_catalog.py`.
  Mirror the upstream `hub_search_tools` contract (`results[].gateway`) and
  retain `matches[].gateway` only as a compatibility form. Expansion must
  accept only explicit known gateway fields; never scan prompt text,
  descriptions, `tool`, `callAs`, or arbitrary result strings for tool names.
- Keep Hub Information Driver discovery, refresh/update-check commands, bounded
  polling, identity reconciliation, units, and snapshot shaping in
  `hub_info_service.py`. Do not move tool visibility, evidence authority,
  receipt emission, or user-facing presentation into that service.
