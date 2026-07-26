# Hubitat MCP AI 0.10.153

## Changed

- Consolidated Claude-first structured interpretation, subjective goal
  handling, semantic natural targets and exact combined-level grammar in
  `control_agent_combined_level.py`.
- Preserved the existing module-object patch points through an explicit
  consolidated self-alias.
- Kept Claude normalization and semantic target normalization in distinct
  private helpers so their parsing contracts cannot overwrite each other.
- Redirected focused interpretation tests to the live combined-level owner.

## Removed

- Removed three superseded sibling-only modules:
  `control_agent_claude_first.py`, `control_agent_goal_based.py` and
  `control_agent_semantic_target.py`.

## Validation

- AST equivalence checks for all 20 moved interpretation functions, normalizing
  only the three deliberate private-helper aliases.
- Claude-first, goal-based, semantic-target, combined-level, gate and unified
  agent focused suites.
- Import and cluster analysis.
- Repository layout validation.
- Python compilation.
- Blocking release gate.
