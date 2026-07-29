# Hubitat MCP AI

Home Assistant add-on providing a native Ollama Online function-calling bridge
to kingpanther13's Hubitat MCP Rule Server.

Current add-on version: **0.10.237**.

## Architecture

FastAPI sends requests directly to `UnifiedMCPAgent`. The agent loads the live
MCP tool catalogue and device manifest, lets Ollama Online select native
function calls, executes those calls through `HubitatMCPClient`, and returns the
final answer. No regex routers, manual entity resolvers, or confidence cascades
are used.

Sensitive MCP mutations require an explicit, session-scoped confirmation.
Read-only gateway operations do not require confirmation.

## Setup

1. Install and configure `MCP Rule Server` on Hubitat.
2. Copy its local MCP endpoint and token.
3. Create an API key in your ollama.com account.
4. Configure the add-on:

   ```yaml
   hubitat_mcp_url: http://192.168.1.100/apps/api/123/mcp
   hubitat_mcp_token: YOUR_HUBITAT_TOKEN
   ollama_direct_cloud_enabled: true
   ollama_direct_cloud_base_url: https://ollama.com
   ollama_direct_cloud_api_key: YOUR_OLLAMA_API_KEY
   ollama_direct_cloud_model: gemma4:31b
   require_sensitive_confirmation: true
   ```

5. Start the add-on and open its Home Assistant sidebar panel.

The WebUI includes live dashboard tiles, smart-home shortcuts, typed and spoken
queries, optional read-aloud answers, response metadata, copy, and expandable
technical details.

## API

- `GET /api/status` — MCP and Ollama Online readiness
- `GET /api/dashboard` — cached live-state dashboard counts
- `POST /api/ask` — process a request through the unified MCP agent
- `POST /api/chat` — compatibility alias for `/api/ask`
- `POST /api/refresh` — refresh MCP tools and device manifest
- `GET /health` — add-on health probe
