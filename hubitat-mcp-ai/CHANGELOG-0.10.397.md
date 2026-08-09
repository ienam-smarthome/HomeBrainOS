# 0.10.397

## Why this release

Second of four grouped releases closing Tier 2 findings from the
proactive full-codebase review conducted earlier this session (release 1
of 4, 0.10.396, shipped light-detection and tool-success consistency).
This release closes a write-safety gating gap.

## Fixed

**`hub_manage_virtual_device`/`hub_manage_mode` could be called with
empty arguments and be waved through as a harmless read.**
`tool_registry.py`'s `_is_gateway_schema_probe()` treats any
`hub_manage_*` tool name called with no arguments as the documented,
harmless "list this gateway's sub-tools" schema-discovery convention,
classifying it as `ToolEffect.READ` -- which skips confirmation gating
entirely. But the connected Hubitat MCP server's own docs are explicit
that `hub_manage_virtual_device` and `hub_manage_mode` are *direct*
tools, not gateways: they don't expose sub-tools, so an empty-args call
to either isn't a safe discovery probe, it's a real invocation attempt.
A model calling either with `{}` (reasonably assuming the same
convention every other `hub_manage_*` name supports) could execute an
unconfirmed, real mutating call instead of triggering schema discovery.
Both tool names are now excluded from the schema-probe check, so an
empty-args call to either falls through to the normal `hub_manage_`
classification path and fails closed to `SENSITIVE_WRITE` (requiring
confirmation) like any other unrecognised `hub_manage_` call.

## Validation

- `python -m pytest -q` -- 725 passed (3 new: `hub_manage_virtual_device`
  and `hub_manage_mode`, called with empty arguments, are now classified
  as `SENSITIVE_WRITE` and require confirmation; an ordinary
  `hub_manage_*` gateway called empty is confirmed to still be treated
  as a safe schema probe).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.397
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- This release closes finding #11 from the full-codebase review
  conducted this session (Tier 2). Pagination/token-estimator robustness
  hardening and apostrophe-free hub-health/firmware phrasing are tracked
  separately as the remaining two grouped releases.
