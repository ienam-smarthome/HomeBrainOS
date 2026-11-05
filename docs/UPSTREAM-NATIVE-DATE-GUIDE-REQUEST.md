# Upstream request draft — document Rule Machine's one-time date field contract

> **Status:** Not filed upstream. On 2026-11-05 the GitHub connector returned HTTP 403 `Resource not accessible by integration` for an issue creation attempt in `kingpanther13/Hubitat-local-MCP-server`. This draft exists for a maintainer or user with write permission to review and submit if appropriate. Do not treat it as a published issue.

Suggested title: **Document native Rule Machine "Certain Time (and optional date)" typed fields in read-only set_rule_reference guide**

## Problem

Upstream MCP Rule Server **v5.1.6** successfully exposes `hub_get_tool_guide(section="set_rule_reference")`. It documents `hub_set_rule(operation="create")` and `parent_id`, but does not name or type the native Rule Machine 5.1 "Certain Time (and optional date)" fields. HomeBrainOS cannot source-attest the installed dated-trigger writing contract without rendering a native rule form, which is intentionally excluded from strict read-only preflight. A readable guide with missing declarations is not evidence of unsupported date functionality.

On 2026-11-05 at 20:11 UTC, HomeBrainOS v0.18.423 verified read-only parent app ID 169, built-in type ID 18, 42 returned linked children, and guide inspection `checked`. The guide lacked `atDate#`, `time#`, `atTime#`, `date#`, `yyyy-MM-dd`, and the Certain Time trigger label. No native editor form or modifying operation was used. Overall readiness remained **Unresolved**, `readinessForMutation=false`.

Upstream #575 was closed by PR #576. That change makes the native model accept the page-declared `date` type, with `yyyy-MM-dd` validation. This requested improvement concerns discoverability/attestation only.

## Requested change

Add an authoritative example to the existing **read-only** `set_rule_reference` guide or an equivalent non-rendering schema projection, making clear whether the field template is static or conditional on the hub's installed Rule Machine page. The prior issue #575 example was:

```json
{
  "part": "trigger",
  "value": {
    "id": "1",
    "capability": "Certain Time (and optional date)",
    "fields": [
      {"name": "time#", "type": "enum", "value": "A specific time"},
      {"name": "atTime#", "type": "time", "value": "2026-11-10T15:35:00.000+0000"},
      {"name": "date#", "type": "bool", "value": true},
      {"name": "atDate#", "type": "date", "value": "2026-11-10"}
    ]
  }
}
```

**Please reverify** capability label, optional date checkbox semantics, year field interactions, atTime value format and required field set against the current native page before elevating this example into a guaranteed contract.

## Suggested acceptance

- The guide or a non-rendering source names the supported trigger field templates/types and documents `yyyy-MM-dd`, or explicitly states which declarations are dynamic and require page-based discovery.
- A static example is distinguished from live on-hub field availability, persisted readback and actual one-time execution.
- No weakening of existing Write master, confirm, recovery/backup requirements, native form validation or credential redaction; no unnecessary extra MCP tools.

Related upstream: [issue #575](https://github.com/kingpanther13/Hubitat-local-MCP-server/issues/575), [PR #576](https://github.com/kingpanther13/Hubitat-local-MCP-server/pull/576), [tracker #561](https://github.com/kingpanther13/Hubitat-local-MCP-server/issues/561).
