# Hubitat MCP AI 0.10.60

- Removes the installable PWA shell from Home Assistant ingress.
- Unregisters legacy HomeBrain service workers and deletes stale shell caches.
- Keeps a temporary cleanup worker endpoint so old registrations retire safely.
- Preserves dynamic runtime version rendering and deterministic guarded app control.
