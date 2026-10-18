# v0.18.31 — Support Claude's tool schema subset without weakening Hubitat execution

## Live root cause (18 October 2026)
v0.18.30 live Claude call returned `Anthropic HTTP 400; type=invalid_request_error; category=tool-schema; tool=homebrain_control_devices; tool_index=14` before executing any MCP command. The offending in-repo definition `tool_registry.control_devices_tool` has top-level `oneOf` requiring exactly one target group, `room` or `device_names`, in addition to the required `device_kind` and `command`. Anthropic tool input schemas explicitly reject root `oneOf`, `allOf`, `anyOf`. The HomeBrain adapter previously validated only the root type and forwarded the unsupported root combinator verbatim.

## Architectural correction
- In the Claude-only schema adapter, handle any **simple root oneOf consisting solely of existing-property required-key groups**. Remove that unsupported root keyword *only from the provider-facing projection*; append unambiguous alternative-group guidance to the tool description and retain all property types, enums, ranges, nested conditions, required keys, and additionalProperties restrictions.
- After Claude generates an action call and **before handing any call to the HomeBrain executor**, validate the proposal against its **original trusted oneOf**: exactly one group may be satisfied. Reject missing or multiple groups with no Hubitat command. The existing `DeviceControlService.execute` independently requires exactly one nonempty `room` or `device_names`, valid kind/command, and valid setpoint/level ranges before execution.
- Do not project unsupported root `anyOf`/`allOf` or complex `oneOf` branches without a trustworthy semantic recheck; fail closed before requesting the provider.
- Continue to avoid changes to the Ollama tool schemas, model selection, paid Free-default routing, sensitive-command confirmation gates, API keys, and MCP permissions.

## Regression
Tests cover the actual rejected `homebrain_control_devices` schema, projection without mutating source definitions, all valid enums and required properties, missing/both group rejection *before dispatch*, either valid target choice, and failure of nontranslatable compositions.

## Remaining live verification
The particular rejected top-level `oneOf` is fixed in code; **the live Anthropic API call remains untested in this release**. After updating the add-on, rerun one read-only Claude question, then (if appropriate) test tool responses. A new indexed provider error would identify another incompatible MCP schema rather than an API key or billing fault. Anthropic charges may apply only when the user explicitly selects Claude.
