# HomeBrainOS repository

A Home Assistant add-on for a Hubitat-based smart home.

Short GitHub description: Local-first AI smart-home assistant for Hubitat + Home Assistant, with event-driven state, verified evidence, and privacy-preserving local control.

## Component

| Component | Version | Status | Purpose |
| --- | --- | --- | --- |
| [Hubitat MCP AI](hubitat-mcp-ai/README.md) | 0.10.373 | Maintained | MCP-backed assistant, verified reads, deterministic controls, bounded device-event history, and optional AI synthesis |

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

Then install **Hubitat MCP AI** from the Add-on Store. See
[`hubitat-mcp-ai/README.md`](hubitat-mcp-ai/README.md#setup) for the Hubitat MCP
Rule Server setup and required configuration options.
