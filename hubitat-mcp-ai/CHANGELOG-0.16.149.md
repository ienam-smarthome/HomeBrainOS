# HomeBrainOS v0.16.149 — global scheduler-probe cleanup guard

v0.16.148 proved the deterministic repair executes, but synthesis can repeat the same unsupported missing-device cleanup claim after leaving the MCP Rule Server subsection. This release makes the guard fail closed across generic recommendation sections when the claim references the known scheduler probe IDs / missing-device references.

It also treats `no longer present` as an unsupported deletion inference for these unresolved IDs.

Regression coverage reproduces the v0.16.148 hypothesis plus generic `Configuration Audit` recommendation shape.

No Hubitat state is changed.
