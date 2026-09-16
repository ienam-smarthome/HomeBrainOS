# 0.10.429

- Reconcile request-level MCP timing with nested `hub_*` evidence emitted by local `homebrain_*` adapters, so slow live Hubitat reads can no longer disappear from the technical metrics.
- Add a `Local tool path` duration to Technical details, making long-running local adapters such as `homebrain_active_rooms` visible alongside provider, MCP, discovery, verification, and total timings.
- Preserve existing direct-MCP timing without double-counting by treating nested evidence duration as a floor rather than adding it again.
- Add regression coverage for the live-observed case where `hub_read_devices` took about 41 seconds while the old MCP metric showed only the 457 ms discovery call.
