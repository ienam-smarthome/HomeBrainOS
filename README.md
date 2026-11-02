# HomeBrainOS repository

A Home Assistant add-on for a Hubitat-based smart home.

Short GitHub description: Local-first AI smart-home assistant for Hubitat + Home Assistant, with event-driven state, verified evidence, and privacy-preserving local control.

## Standing development direction

**[Answer Quality Charter](docs/ANSWER-QUALITY-CHARTER.md)** · **[Current benchmark status / cross-chat handoff](docs/ANSWER-QUALITY-STATUS.md)** · **[Agent instructions](AGENTS.md)**

HomeBrainOS development is now **benchmark-first**. Target Claude-quality natural, source-grounded smart-home answers; do not change direction between chats, endlessly patch one incident, or interpret green unit tests as measured AI accuracy. The existing 13-task golden inventory and 18 curated review cases form an initial **31-case definition set** toward a 40–50-case benchmark. Human-graded production answer quality is **not yet measured**.

Run `python scripts/answer_quality_scorecard.py` for an honest `not_measured` baseline. Add independently reviewed, source-referenced answers before reporting scores. User assistance is needed primarily for specific HomeBrain read-only question/answer captures.

## Component

| Component | Version | Status | Purpose |
| --- | --- | --- | --- |
| [Hubitat MCP AI](hubitat-mcp-ai/README.md) | 0.18.348 | Maintained | Capability-grounded semantic smart-home agent with AI intent planning, deterministic verified execution, bounded history, and grounded synthesis |

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