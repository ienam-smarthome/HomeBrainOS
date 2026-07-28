# Hubitat MCP AI 0.10.206

- Discover the live device manifest through the current 36-tool server's
  `hub_read_devices` category gateway.
- Decode nested gateway results into the cached device manifest.
- Explicitly teach Ollama the gateway `tool`/`args` call contract for device
  reads.
