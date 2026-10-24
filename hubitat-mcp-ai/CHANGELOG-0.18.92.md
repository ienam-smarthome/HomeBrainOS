# HomeBrainOS 0.18.92 — Single-device forensic scope ahead of full-hub audit

## 24 October 2026 comparison

The exact same read-only question about **Bedroom 3 Mesh (device 7103)** was sent to HomeBrain 0.18.91 and Claude. HomeBrain responded after **42.5 seconds**, but selected `comprehensive-system-audit`: read a 204-device inventory, 160 app inventory, 278 scheduled entries and top-20 performance rows, then sent the report to an **optional tool-free AI adviser**. Its AI could not follow the target device's event history, retrieve the 20,531-character installed Tasmota MQTT driver, inspect rule 3950, test network reachability or independently verify that the driver `mqttStatus=connected` reflected the hub-to-broker link rather than plug communication.

Claude's longer investigation established the *last confirmed* device message (12 October 2026, 01:30:01 BST), the associated rule OFF timing, later status-event noise, sibling plug status and failed ICMP echo to the plug while the router replied. Physical root cause remained unverified. The model also noted that a parent MQTT configuration page had exposed a credential in raw MCP output: separately review and redact MCP secrets before passing tools to any external model.

## Scope bug and fix

The broad System Check classifiers interpreted words such as `comprehensive`, `app`, `device`, `logs` and `scheduled jobs` as a whole-hub audit, even though the request explicitly named exactly one device and requested its root cause. The resulting fast path deliberately prevented additional AI MCP calls.

- Introduce `targeted_device` into the existing immutable `InvestigationObjective`, with one explicit device ID and no explicit whole-hub target scope. This selects a tool-led investigation without asserting the current installed device identity or authorising a probe/write.
- Apply this primary objective to the **API route before choosing any broad audit or performance shortcut**. An explicit single-device incident stays with the iterative model-led MCP agent even if it requests cross-domain tools (driver code, event history, app settings, scheduling and performance).
- Make both comprehensive and cross-domain whole-hub classifiers respect the same explicit single-device objective. Explicit full-system/whole-hub requests remain on their established fast report route, including when they name a device as an example.
- Add regression tests reproducing the full user question and independent broad/targeted scope cases.

## Limits

This change gives the model access to its ordinary iterative MCP read path, instead of a bounded System Check plus tool-free commentary. It does **not** guarantee Claude-equivalent source selection, a particular number of tools, physical ICMP checks, completeness of Hubitat's event-history retention, or a verified hardware root cause. Permission checks and Hubitat write confirmation remain unchanged; no live hub modification was made.

The source report's permission prompts are interaction controls, not evidence that a model reasoned better. For HomeBrain, read-only tool calls can be executed without prompting only when already authorised; write operations retain user confirmation. Additionally, sensitive values in MCP configuration responses should be redacted at the server boundary, not trusted to the model to omit from final text.
