# Hubitat MCP AI 0.10.87

## Unified assistant reliability and runtime cleanup

- Improved targeted MCP device recovery by extracting the requested device name before authoritative lookup.
- Strengthened planner guidance so discovery tools are followed by authoritative MCP reads.
- Centralized release metadata in `release_version.py`.
- Updated repository validation and current release tests to use the shared version source.
- Made historical regression audits explicitly non-blocking while retaining the 244-test release gate.
- Removed obsolete PWA manifest, service-worker, installation and cache-cleanup support.
- Preserved the normal Home Assistant ingress Web UI.
- Migrated FastAPI startup and shutdown handling from deprecated event decorators to lifespan management.
- Preserved device-index warming, active-request cancellation, and MCP/Ollama client shutdown behavior.
