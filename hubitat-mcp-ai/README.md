# Hubitat MCP AI

Home Assistant add-on providing a native Gemini function-calling bridge to
kingpanther13's Hubitat MCP Rule Server.

Current add-on version: **0.10.199**.

## Architecture

Requests flow directly from FastAPI to `UnifiedMCPAgent`. The agent loads the
live MCP tool catalogue and device manifest, lets Gemini select native function
calls, executes those calls through `HubitatMCPClient`, and returns Gemini's
final response. There are no regex pre-routers, entity resolvers, confidence
gates, or Ollama fallback chains in the active runtime.

Sensitive or destructive MCP tools are enforced in code and require an explicit
confirmation tied to the browser or API session before execution.

## Setup

1. Install and configure `MCP Rule Server` on Hubitat.
2. Copy its local MCP endpoint.
3. Create a Gemini API key in Google AI Studio.
4. Configure the add-on:

   ```yaml
   hubitat_mcp_url: http://192.168.1.100/apps/api/123/mcp
   hubitat_mcp_token: YOUR_HUBITAT_TOKEN
   gemini_api_key: YOUR_GEMINI_API_KEY
   gemini_model: gemini-3.6-flash
   require_sensitive_confirmation: true
   ```

5. Start the add-on and open its Home Assistant sidebar panel.

The complete endpoint may instead include `?access_token=...`; in that case,
leave `hubitat_mcp_token` empty. Tokens and API keys are Home Assistant password
options and are not included in responses or diagnostics.

## API

- `GET /api/status` — MCP and Gemini readiness
- `POST /api/ask` — process a request through the unified MCP agent
- `POST /api/chat` — compatibility alias for `/api/ask`
- `POST /api/refresh` — refresh the MCP tool catalogue
- `GET /health` — add-on health probe

Home Assistant ingress uses relative API paths, while direct access remains
available at `http://HOME_ASSISTANT_IP:8788`.
