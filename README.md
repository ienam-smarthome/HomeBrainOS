# HomeBrainOS repository

A Home Assistant add-on for a Hubitat-based smart home.

Short GitHub description: Local-first AI smart-home assistant for Hubitat + Home Assistant, with event-driven state, verified evidence, and privacy-preserving local control.

## Component

| Component | Version | Status | Purpose |
| --- | --- | --- | --- |
| [Hubitat MCP AI](hubitat-mcp-ai/README.md) | 0.10.287 | Maintained | MCP-backed assistant, verified reads, deterministic controls, bounded device-event history, and optional AI synthesis |

The legacy/alternate HomeBrain OS dashboard (Maker API-based, `homebrainos/`)
has been retired and removed from this repository. All assistant development is
centred on Hubitat MCP AI; see
[`hubitat-mcp-ai/README.md`](hubitat-mcp-ai/README.md) for architecture, setup,
and configuration.

## Install on Home Assistant OS

Add this repository URL in the Home Assistant Add-on Store:

```text
https://github.com/ienam-smarthome/HomeBrainOS
```

Then install **Hubitat MCP AI** from the add-on list. See
[`hubitat-mcp-ai/README.md`](hubitat-mcp-ai/README.md#setup) for the Hubitat MCP
Rule Server setup and required configuration options.

The assistant WebUI and control API are exposed through authenticated Home
Assistant ingress. Direct host-port access is disabled by default.

## Security

Never commit Hubitat MCP tokens, Ollama API keys, local IP credentials, `.env`
files, or database/cache files containing personal home data.

## Repository layout

- `hubitat-mcp-ai/` — the add-on (see
  [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the request-handling
  architecture and consolidation history)
- `backend/`, `frontend/` — early scaffolding, not part of the shipped add-on
- `android-wrapper/` — Android wrapper app build
- `tests/`, `scripts/` — repository-wide validation and test tooling
- `docs/` — architecture, contributing, and workflow reference
