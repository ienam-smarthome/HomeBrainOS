# Hubitat MCP AI 0.10.62

## Authoritative rendered version

- Uses the version baked into the running Home Assistant add-on image as the single runtime source of truth.
- Rewrites the generated page's JavaScript `VERSION` value after all legacy renderers and Web UI patches have run.
- Adds `GET /api/runtime-version` with `baked_version`, `application_version`, `api_version`, and `rendered_version`.
- Raises a startup/request error instead of silently serving a page when the final version declaration cannot be identified safely.
- Retains deterministic app control, PWA retirement, and cache-clearing behaviour from earlier releases.
