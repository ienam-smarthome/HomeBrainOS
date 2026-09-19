# Hubitat MCP AI 0.14.14

## Home Assistant TTS token compatibility

- Request the compatible Supervisor API grant in addition to
  `homeassistant_api: true` so live Home Assistant installations reliably
  inject an API token into the add-on container.
- Use the least-privilege `default` Supervisor role; Home Assistant Core API
  access remains separately granted by `homeassistant_api: true`.
- Continue using the Home Assistant Core API proxy at
  `http://supervisor/core/api`.
- Accept the legacy `HASSIO_TOKEN` environment variable as a compatibility
  fallback when `SUPERVISOR_TOKEN` is not present.
- Never expose either token in the WebUI or API responses.
- Preserve S25/WebView target matching and the native Android TTS flow from
  0.14.13.
- Add regression coverage for the compatibility token path.
