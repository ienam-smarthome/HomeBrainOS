# Hubitat MCP AI 0.10.237

- Accepts the direct single-device object returned by `hub_get_device`.
- Supports the same record when nested beneath gateway `device`, `result`,
  `data`, `output`, or `content` wrappers.
- Fixes Hub Info firmware checks incorrectly discarding valid detail records
  and polling until `Hub Info attributes were unavailable after refresh`.
- Updates regression coverage to mirror the live MCP response contract.
