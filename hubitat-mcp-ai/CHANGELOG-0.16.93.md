# Hubitat MCP AI 0.16.93

## Capability-grounded device resolution

- Fixes scheduled Internet-control requests that resolved a similarly named ordinary device instead of the dedicated Internet-control device.
- When `required_command` is supplied, a targeted exact-name row that does not advertise that command is no longer accepted as terminal.
- An empty capable subset now deliberately activates the existing authoritative identity fallback, which is itself filtered by the required command before fuzzy name matching.
- Live regression covered: `Google TV Streamer (ADB)` must not win a `blockInternet` request over `Block Media-Google-TV-Streamer`.
- Ordinary device resolution with no required command is unchanged.
- If no capability-grounded target can be resolved, Rule Authoring fails closed and reports that no matching device advertising the required command could be resolved, rather than implying that an incapable exact-name device was selected.
- No change to scheduling grammar, Rule Machine payloads, or Internet switch semantics (`on` = Internet allowed, `off` = Internet blocked).
