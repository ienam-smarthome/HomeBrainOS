# Hubitat MCP AI 0.10.263

- Disabled the add-on's direct host-port mapping by default.
- Kept the WebUI and control API available through authenticated Home Assistant ingress.
- Documented that direct port exposure requires an authenticated reverse proxy or equivalent protection.
- Added regression validation for the ingress-only default.
