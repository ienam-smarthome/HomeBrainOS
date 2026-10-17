# 0.18.16 — Distinguish source-class checks from upstream and physical evidence

## Live finding
The v0.18.15 investigation of Bedroom 3 Mesh successfully proposed three candidate explanations and retained them in the final report. However, its first hypothesis asked whether device-originated MQTT messages had reached the broker while a Hubitat device log read was labeled a checked evidence source. Merely checking the Hubitat log source class cannot answer that upstream-packet question.

## Improvement
- Add a bounded origin requirement to each optional model-proposed hypothesis discriminator: `hubitat`, `upstream`, `physical`, or `unspecified`. The model proposes its required origin; no arbitrary source or tool names are accepted.
- The existing evidence checkpoint reports evidence **class** separately from required source **origin** and expressly refuses to certify upstream broker/telemetry or physical delivery based on the currently available Hubitat-only source receipts.
- A class-checked upstream/physical discriminator remains in the missing-evidence questions, with `discriminator_verified=false` and an unverified hypothesis verdict.
- The final safe evidence report states when an independent upstream or physical source is not verified, instead of labeling a source-class query as a completed discriminator.
- Keep previously working source-class accounting intact. No hardcoded device IDs, model-round increases, new MCP methods or device-specific fixes.

## Limitations
This release **does not** automatically validate or rank hypotheses from the content of returned log lines, trace driver-source control flow or independently read MQTT broker packets. A future evidence-fact comparison step must validate typed, scoped corroboration and contradiction. A model can still misclassify a requirement; the host never upgrades a checked source category into causal proof.

## Safety and test coverage
No new write authority, credential access or permission bypass. Regression tests cover Hubitat device logs vs upstream broker packets, device command history vs physical acknowledgements, bounded model-origin validation and preservation of the explicit uncertainty in the final response. All three standard GitHub workflows required before merge. Home Assistant live testing remains separate.
