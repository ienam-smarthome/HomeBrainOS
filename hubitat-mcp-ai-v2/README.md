# Hubitat MCP AI v2 — clean pilot

**Separate experimental add-on**; does not replace or update the existing `hubitat-mcp-ai` add-on. V2 is built as a new implementation, not a refactor of v1. No legacy answer-quality patches, forced investigation recipes, deterministic answer rewriting, evidence-score engines, Stage 4–7 benchmark pipeline or fixed model/tool round quotas are loaded.

## What v2 includes

1. A direct native Ollama `/api/chat` agent that chooses and calls live Hubitat MCP read tools without predetermined investigative steps. Tool schemas come from `tools/list`; no handwritten Hubitat schema registry.
2. One short, readable Hubitat MCP skill, adapted from the upstream MIT-licensed skill. The model chooses whether to read a guide, lookup, history, app configuration, logs or other available sources.
3. A tiny Ask/Chat web UI and transparent tool-call receipts (no invented JSON evidence).
4. The **exact same** `external_hub_diagnostics.py` source blob as v1, with its persistent SQLite storage, 30–300s external free OS probes, native five-minute Java/load samples, confirmed `systemStart` markers, connectivity incidents, downsampled histories, 1h–30d windows and 30d default retention.
5. No Historical Journal, Rule Machine shortcut, v1 router, v1 reasoning patch or scheduler.

The first v2 experiment is **read-only**. This is not an answer-quality restriction; no live write/control tools are exposed. Permissions, timeouts, restricted secrets and server-side read/write masters are not optional AI reasoning features.

## Setup

Home Assistant → Settings → Add-ons → Add-on Store → your HomeBrainOS repository → **Hubitat MCP AI v2 (Preview)** → Install. Existing v1 may stay installed and running. Do **not** uninstall v1 or change Hubitat settings for this experiment.

Configure:
- `hubitat_mcp_url`: exact local MCP Streamable HTTP URL (can contain its normal endpoint path)
- `hubitat_mcp_token`: token, if the endpoint requires the `access_token` query parameter
- `model_base_url`: Ollama-compatible base URL, e.g. `https://ollama.com` for Ollama Cloud or `http://WINDOWS-LAN-IP:11434` for Ollama locally
- `model_name`: tool-calling model supported by that endpoint
- `model_api_key`: required for Ollama Cloud, leave blank for local Ollama
- Optional: `external_hub_diagnostics_enabled: true`, `external_hub_diagnostics_hub_url: http://HUB-LAN-IP`, logical cores = 4 for C8 Pro; probe 30s; retention 30d.

Use Home Assistant sidebar ingress. The optional direct port is disabled by default. No credentials or complete MCP responses are saved to the recorder.

**Existing v1 recorder data is NOT automatically shared with the new add-on:** each add-on has its own `/data` folder. Copy/restore its existing SQLite database through a deliberate separate migration if historical continuity is needed. Starting v2 creates a new recorder history.

## API

- `POST /api/ask` body `{"question":"Why did Livingroom Light 2 turn off?", "history":[]}`. Response `success`, `answer`, `tool_calls`, `elapsed_ms`.
- `GET /api/status`: configuration/read-only health, no credentials.
- `GET /api/diagnostics/status`, `/history?metric=free_os_mb&hours=24`, `/timeline?hours=24`: read local SQLite only.
- `GET /`: mobile-friendly Ask and Hub Diagnostics.

## First acceptance benchmark

Run each question on **identical** read-only Hubitat source data where possible, and retain raw answers/receipts: most recent Livingroom Light 2 OFF; bathroom humidity over 70% then below 60%; heating interval and TRV demand; hub memory/reboot incident. Assess verified conclusions, unsupported assertions, completeness, latency and source failures. No claim of higher model accuracy until live tests.

Operational limits (per call timeout and user request deadline) remain so a stalled model cannot hang indefinitely. There is no artificial model-round limit or answer rewriting.

## Rollback

Stop/uninstall the **v2** add-on; v1, Hubitat and all devices remain unchanged. No automatic promotion to v1/main deployment.
