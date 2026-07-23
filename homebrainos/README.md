# HomeBrain OS dashboard

Version **1.9.55-alpha**.

This is the legacy/alternate Home Assistant add-on in the HomeBrainOS
repository. It connects to Hubitat through Maker API and provides the original
dashboard, device cache, room intelligence, and local assistant.

It is distinct from the maintained
[Hubitat MCP AI add-on](../hubitat-mcp-ai/README.md), which uses the Hubitat MCP
Rule Server and has its own `0.10.x` release series.

## Installation

Install the `homebrainos` add-on only when you specifically want the Maker API
dashboard. Its web interface is exposed on port `8787`.

For the current MCP-backed assistant, install `hubitat-mcp-ai` instead.
