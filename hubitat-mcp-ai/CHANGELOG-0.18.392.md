# Hubitat MCP AI v0.18.392 — Problem-first automation status

## Scope and evidence

A single user-provided live v0.18.391 status response returned 165 deduplicated configuration items (146 non-disabled, 18 disabled, 1 paused) with no broken flags, yet said "1 need attention" solely because an intentionally paused rule was counted and printed all 165 entries. The source records support a configuration inventory, **not** verified rule execution.

## Change

- For ordinary queries covering >40 automation entries, give a compact status total, separate broken/unknown from paused/disabled, show up to ten problem/uncertain/paused names, and summarize omitted routine active/disabled entries. No model or tool rounds added.
- Count broken and unknown configurations for the headline attention count, *not a paused rule by itself*. Do not claim a paused rule is healthy or firing; it is configured to pause.
- "List every/all/full..." still returns the entire formatted listing. All requests retain the complete machine-readable `automation_items` and underlying evidence in Technical JSON.
- Existing small-inventory and explicit broken-query responses retain their paths.

## Verification and limitations

Synthetic 165-entry regression tests, explicit full inventory selection, paused-not-broken checks; full Python/CI results are linked from the PR. Expected effect: shorter and more semantically accurate normal automation status answers. Actual installed first-answer accuracy/usefulness/latency effect **NOT MEASURED**. Runtime rule health still requires independent logs, actions and dependencies.

## Safety / rollback

Only read-only response rendering and status-intent routing change; no live Hubitat/HA/router writes or rule edits. Revert this release if status questions lose required entries or explicit full inventories fail.
