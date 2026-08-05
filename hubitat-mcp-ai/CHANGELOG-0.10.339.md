# Hubitat MCP AI 0.10.339

## Changed

- Extracts rule-authoring proposal confirmation handling out of
  `mcp_agent_orchestrator.UnifiedMCPAgent._process_user_request` into a new
  `rule_proposal_confirmation.py` module (`RuleProposalConfirmation`),
  following the same constructor-injected-dependencies pattern already used
  by `ConfirmedActionCoordinator` and `DirectOutcomeContext`.
- No behavior change: same confirmation-policy evaluation, same queuing,
  same message construction, byte-for-byte identical control flow -- only
  relocated and given its own constructor and tests.
- `mcp_agent_orchestrator.py` drops from 999 to 980 lines (1,026 before the
  0.10.338 catalog-assembly extraction).

## Validation

- Adds `tests/test_rule_proposal_confirmation.py`: direct-message passthrough,
  action queuing, default-session rejection, and disabled-policy bypass.
- Adds `rule_proposal_confirmation.py` to `docs/RUNTIME-MODULE-MAP.md`.
- `python3 -m pytest -q` (506 passed).
- `python3 scripts/analyze_imports.py` reports zero orphan modules.
- `python3 scripts/validate_addon.py` (repository layout and version
  alignment OK).

## Note

Two extractions down (local-tool catalog assembly in 0.10.338, rule-proposal
confirmation here); the provider tool-calling loop, the outer confirmation
resume path, and outcome construction inside `_process_user_request` are
still the largest remaining seams and are more deeply coupled to `self`
state -- each needs its own focused pass rather than one large rewrite.
