---
name: hubitat-operations
description: Read/write-safe operation of the live Hubitat MCP Rule Server; tool discovery, native apps, device matching, and efficient evidence retrieval.
version: 1
origin: Adapted from kingpanther13/Hubitat-local-MCP-server agent-skill/hubitat-mcp (MIT).
---
# Hubitat MCP operating skill

The connected MCP server's live catalog and hub_get_tool_guide are authoritative. Do not assume tool names, parameters, permissions, or feature support from a previously generated skill document.

## Discovery
Discover narrowly through hub_search_tools with a *capability phrase*, not the full user prompt. Read only a relevant hub_get_tool_guide section. A hub_read_* gateway exposes read-only operations. hub_manage_* can contain writes; inspect leaf semantics and server gates before calling. Tool availability and the original user's authorisation are separate requirements.

## Efficient reads
Resolve exact names/IDs first (hub_list_devices with labelFilter, fields or detailed=false). Prefer targeted hub_get_device, scoped hub_list_device_events and filtered hub_get_logs. Use small limits, event-time since/until, pagination and requested field projections. The hub is single-threaded: default to sequential calls; don't flood it with parallel requests. Never mistake a successful history query or an empty bounded window for full historical coverage.

## App configuration and topology
For each relevant app or rule, inspect its configuration, not just its label. hub_list_app_pages and hub_get_app_config can expose nested pages and conditional inputs. Find controller and light device IDs, subscriptions, activation sensors, trigger conditions, action paths, timers and external MQTT/bridge inputs. Configuration describes what *could* happen, not whether it ran at a past time.

## Distinguish evidence
A Hubitat device command event proves an invocation was recorded. A reported switch event proves Hubitat observed a state report, not who initiated it. producedBy is the producer of that particular event; triggered[] contains downstream listeners. A physical bridge event does not exclude an earlier Hubitat command. Device events are not physical acknowledgements unless separate transport evidence confirms them.

## Write safety
Never change devices or rules as part of a read-only investigation. Confirm non-exact device matches before writes; don't silently substitute. Respect Read/Write masters, advanced overrides, confirmations, and fresh backup requirements for destructive operations. Never read or expose secrets unnecessarily; redact MQTT passwords and credentials. Do not claim a write succeeded without checking an acknowledgement or resulting state.

Source reference: https://github.com/kingpanther13/Hubitat-local-MCP-server/tree/main/agent-skill/hubitat-mcp
