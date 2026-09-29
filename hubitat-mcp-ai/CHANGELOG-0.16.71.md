# Hubitat MCP AI 0.16.71

## Summary

0.16.71 keeps the 0.16.70 four-tool / single-final-synthesis performance architecture and hardens only the deterministic grounding and formatting layer after the 0.16.70 live proof.

## Changes

- Make `performance_live_semantic_guard.py` Markdown-aware:
  - repair prose lines independently;
  - repair Markdown table cells independently;
  - preserve table columns, headings, bullets, and recommendation rows during deterministic corrections.
- Fail-close the exact 0.16.70 unsupported claims:
  - bottlenecks “caused by” blocking calls or synchronized scheduling;
  - thread blocking / stalled hub operations inferred from high average execution time;
  - scheduler alignment promoted to CPU spikes, UI stuttering, delayed automations, or hub overhead;
  - frequent device reporting promoted to constant overhead;
  - database size described as “within normal limits” without a current-turn threshold;
  - unsupported “primary cause” performance wording.
- Neutralize dramatic causal headings such as “Scheduling Thunder-Claps”, “Blocking Device Execution”, and “High-Frequency Reporting & Overhead”.
- Gate `Run a Z-Wave repair` recommendations on Z-Wave-specific diagnostic evidence (node/route/topology/mesh/repair-status detail). `zwHealthy:false` alone now supports inspection, not a repair prescription.
- Add the full 0.16.70 live answer as a regression fixture and assert that repaired recommendation tables retain all three columns and all rows.

## Architecture retained

- Request-local normalized/privacy-redacted performance evidence packet.
- Normally four read-only tool calls for a broad performance recommendation request.
- One final performance provider synthesis call.
- Normally three total model rounds when the original agent uses two rounds.
- Deterministic repair instead of a second cloud-model repair request.

## Live proof target

Run:

`Analyse my Hubitat performance and recommend improvements.`

Expected:

- `version: 0.16.71`;
- normally `tool_calls: 4` and `model_rounds: 3`;
- database size remains in MB without unsupported “normal limits” wording;
- no unsupported thread-blocking, CPU-spike, UI-stutter, delayed-automation, constant-overhead, or primary-cause claims;
- no Z-Wave repair recommendation from `zwHealthy:false` alone;
- intact three-column recommendations table after deterministic repair.