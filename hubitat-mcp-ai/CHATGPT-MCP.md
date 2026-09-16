# ChatGPT MCP support

HomeBrainOS can expose a small Streamable HTTP MCP surface for ChatGPT while keeping the existing Hubitat MCP client, deterministic device resolution, evidence recording, confirmation policy and verified execution path in charge of smart-home work.

## What is exposed

The endpoint is `POST /mcp` and advertises three tools:

- `homebrain_status` — read-only HomeBrainOS/Hubitat/provider health.
- `homebrain_dashboard` — read-only dashboard snapshot.
- `homebrain_ask` — routes a smart-home request through the existing `UnifiedMCPAgent`. This tool is marked write-capable because requests can control devices or change automations. Existing HomeBrainOS confirmation and verification rules still apply.

The MCP server supports `initialize`, `notifications/initialized`, `ping`, `tools/list` and `tools/call`. It uses JSON responses over Streamable HTTP; the optional GET/SSE stream is intentionally not implemented.

## Enable it

The feature is disabled by default. In the Home Assistant add-on configuration set:

```yaml
chatgpt_mcp_enabled: true
chatgpt_mcp_require_bearer_auth: true
chatgpt_mcp_token: "use-a-long-random-secret"
```

Restart the add-on after changing the options.

Bearer authentication is required by default. If a trusted Secure MCP Tunnel provides the authentication boundary and cannot inject an `Authorization: Bearer ...` header, you can set:

```yaml
chatgpt_mcp_require_bearer_auth: false
```

Do **not** disable bearer authentication when exposing port 8788 directly to a network you do not fully trust. Direct port mapping remains disabled by default.

## ChatGPT connectivity

ChatGPT does not connect directly to private/LAN-only MCP servers. Use OpenAI Secure MCP Tunnel (or another appropriately authenticated remote endpoint) and point the ChatGPT custom app at the tunnel's `/mcp` URL.

For full MCP write/modify actions, use a ChatGPT plan/workspace that currently supports full custom MCP apps. ChatGPT can then scan the tools and invoke `homebrain_ask`; HomeBrainOS remains the execution/safety layer between ChatGPT and the Hubitat MCP Rule Server.

## Session and confirmations

HomeBrainOS returns an `Mcp-Session-Id` during initialization. The client should send that header back on subsequent MCP requests. `homebrain_ask` uses the same value as its HomeBrainOS `session_id`, which keeps pending confirmations and device-disambiguation context scoped to the MCP conversation.

A sensitive request may therefore work like this:

1. ChatGPT calls `homebrain_ask` with the requested change.
2. HomeBrainOS returns a confirmation-required response.
3. ChatGPT asks the user to confirm.
4. After explicit confirmation, ChatGPT calls `homebrain_ask` again in the same MCP session.
5. HomeBrainOS revalidates, executes and verifies the change using its existing control path.

## Architecture

```text
ChatGPT
   |
   | MCP (Secure MCP Tunnel / authenticated remote endpoint)
   v
HomeBrainOS / Hubitat MCP AI
   |-- MCP transport: /mcp
   |-- UnifiedMCPAgent
   |-- confirmation + verification
   |-- deterministic resolution + evidence
   v
Hubitat MCP Rule Server
   v
Hubitat C-8 / C-8 Pro
```

The existing Home Assistant WebUI and `/api/*` endpoints continue to work unchanged.
