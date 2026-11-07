# Hubitat MCP AI v2 — clean-room pilot status

Date: 2026-11-07
Repository: `ienam-smarthome/HomeBrainOS`
Development branch: `feat/hubitat-mcp-ai-v2-clean-rebuild`
Version: `2.0.0-alpha.1`

## Decision

The user observed that Thaura AI's free service connected to the same upstream Hubitat MCP server answered a home incident question well. Rather than add another HomeBrain per-question causal/answer patch, build an isolated **model-led v2** using native MCP tool discovery and a concise upstream-inspired skill. The experiment tests whether the model autonomously chooses and follows up on the right sources, without the old deterministic reasoning scaffolding.

**This is a new app, not a destructive rewrite of HomeBrainOS v1.** Leave `hubitat-mcp-ai/`, its data and deployment untouched.

## Implemented in candidate source

- Independent Home Assistant add-on `hubitat-mcp-ai-v2/` with unique slug `hubitat_mcp_ai_v2`, ingress port 8789 and optional direct port disabled.
- A direct Ollama-compatible `/api/chat` function-calling loop; the model discovers live read tools from MCP `tools/list`, selects tool calls and receives unmodified-in-substance read receipts except for credential redaction and large-payload truncation explicitly marked as such.
- No specialized causal router, no fixed round quota, no incident-specific planners, no rewriting generated conclusions, no staged claim guards, no Rule Machine inventory shortcut and no v1 historical journal.
- A short `SKILL.md` with guidance adapted from the upstream MIT Hubitat MCP skill; live schemas remain authoritative.
- Exact unchanged `external_hub_diagnostics.py` blob copied from v1, in an independent persistent SQLite file. Native reported load equivalent must not be described as measured CPU utilisation; a connection incident or systemStart is not proof of a memory-failure cause.
- Compact Ask/Chat page and responsive graphical external recorder page with selected time windows, independent OS-memory/CPU axes, retained native timestamps, dotted grids/hover crosshairs and observed startup/outage markers.
- Minimal tests and v2-only workflow.

## Deliberate retained boundaries

The pilot is **read-only**. Only native read-tool names and `hub_read_*` gateways are presented; write/manage/call-device/reboot functions are not invocable. This is an experiment boundary, not a limitation on investigation sophistication. Retain hub permission gates, exact source tool schemas, credential redaction, operational timeouts and safe Hubitat probe cadence.

A future v2 with control capabilities would require new explicit user authorization and independent write-safety review, rather than automatically inheriting v1 permission options.

## Diagnostics migration

The recorder implementation is retained, but v2 cannot read v1's `/data` by default. V2 starts a new SQLite history file. Preserving v1 data in v2 requires a deliberate copy/migration after deployment; do not claim the historical samples automatically transfer.

## Test plan (not yet live-verified)

1. GitHub Python compile/unittest on exact v2 branch; optional add-on build smoke in a disposable HA environment.
2. Install v2 alongside v1, retain v1, configure known MCP URL and existing Ollama free cloud/local model credentials.
3. Read-only repeat tests: Livingroom Light 2 most recent OFF; bathroom humidity >70% until <60%; thermostat heating intervals and TRV demand; memory/reboot incident.
4. Compare with v1, Claude and Thaura only where source evidence/time window/model capabilities are known and comparable; record first-answer utility, exact tool receipts, unsupported causal claims, incomplete source work, latency and cost.
5. Do not declare v2 superior or production-ready from green unit tests or a few screenshots.

## Current evidence and caveats

This is an alpha candidate. No live Hubitat model call, HA ingress acceptance, recorder source data continuity or deployed test has been verified in this repo-only development pass. Continuous follow-up depends on the user resuming a session; no unattended background development is running.
