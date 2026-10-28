# HomeBrainOS v0.18.181 — Native MCP Read Agent (V2 preview)

## Architecture
V2 now supports a separate model-selected native MCP read loop. The user question reaches the model and live tool manifest before any device-inventory lookup. The agent may investigate hub status, application errors, log patterns, automations and device incidents through sequential source reads. Legacy V2 remains selectable for comparison; production Main Ask is unchanged.

## Safety
Only independently verified read gateways and operations are eligible; management gateways and control arguments are never executed. Source-returned IDs must be verified before targeted follow-up calls. The host bounds tool rounds, latency, request size and evidence projection. Unavailable log reads are explicitly disclosed. Source data and model conclusions are separate. No Hubitat writes or saved System Check changes.

## Tests
Synthetic model-driven tool calls cover whole-hub diagnostics, errors, health, auth, unsafe tool denial, unverified device IDs, watchdog message grouping, credential redaction and inventory-free API entry.

## Limitations
Live provider compatibility, independent causal-claim grounding, source pagination and full benchmark quality require further work. This is an opt-in V2 architecture preview, not a verified claim of Claude-equivalent reasoning. The existing legacy and production paths remain available.
