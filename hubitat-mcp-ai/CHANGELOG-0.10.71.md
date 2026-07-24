# Hubitat MCP AI 0.10.71

- Resolves `application.ask` at request execution time instead of capturing an older handler when `/api/ask` is installed.
- Prevents deterministic terminal routes from being bypassed by later composition changes.
- Ensures **What is thermostat setpoint** reaches the live thermostat reader and uses `hub_read_devices` rather than AI inventory search.
- Adds an HTTP-boundary regression proving a handler installed after route creation is used.
- Validates the exact reported wording through the final cancellable request route.
- Keeps app, Hub-health and future terminal routes order-safe as well.
