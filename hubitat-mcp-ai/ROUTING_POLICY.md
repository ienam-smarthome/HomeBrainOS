# Hubitat MCP AI routing policy

Hubitat MCP AI uses three paths, chosen for speed without sacrificing natural language or state accuracy.

## MCP-fast

Use only for one explicit `turn/switch on/off <target>` command. The deterministic matcher executes and verifies the resulting Hubitat state. If it cannot find one exact safe match, the request is handed to the natural Ollama MCP planner.

## Ollama with verified MCP context

Use for routine read-only questions such as lights on, active motion, weather, batteries, rooms, device health, hub resources and home overviews. The deterministic MCP reader obtains authoritative evidence first; Ollama only writes the concise natural answer. This avoids a slow tool-planning pass and prevents invented device or hub facts.

## Ollama MCP planner

Use for contextual or complex controls, explanations, comparisons, recommendations, troubleshooting and rule/automation work. Ollama selects and combines Kingpanther MCP tools, while sensitive actions still require confirmation.

A new browser question cancels the previous request for that browser client.
