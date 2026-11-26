# Upstream skill provenance

Source: https://github.com/kingpanther13/Hubitat-local-MCP-server/tree/98bc7ca2d0f1bd2e2857962292b33d83683bc2b0/agent-skill/hubitat-mcp
Commit: `98bc7ca2d0f1bd2e2857962292b33d83683bc2b0`
Retrieved: 2026-11-07

SKILL.md and rule-patterns.md are copied without changes from that commit.
safety-guide.md was replaced on 2026-11-26 with a newer upstream copy supplied by
the owner (current waitFor guidance, bundle safety, file-name rules); its commit
is not recorded. Re-sync all three files to one recorded commit when updating.
LICENSE is the upstream repository MIT license.
All three guidance files are loaded by agent.py. Live server schemas and tool
guides remain authoritative. The model's upstream guidance does not replace
server access gates or an explicit user decision for confirm=true calls.

When updating, retrieve the upstream files and license together, record the
new commit and review compatibility. Do not reconstruct a fixed tool inventory.
