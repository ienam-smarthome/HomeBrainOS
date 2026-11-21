# Independent reviewer packet — HomeBrainOS Causal Investigator V3

**Read first:** [RFC-CAUSAL-INVESTIGATOR-V3.md](RFC-CAUSAL-INVESTIGATOR-V3.md). The user wants an evidence-led, autonomously investigating Hubitat/HA assistant, *not* more per-phrase fallback patches.

**Current release:** v0.18.260. Existing model-native agent: `gemma4:31b` via Ollama Cloud, 10 rounds, 24 tool calls, ~58.2 seconds on focal test.

**Focal incident (30 Oct 2026, 14:50–15:30 GMT):**
- Bathroom Lights 1/2 each report five ON/OFF cycles, 20 independent-source-timestamped switch observations total; 20 collector-reception copies. Native histories partly rolled over.
- App 4013 invoked `setLevel(60)` *after* first reported ON; cannot prove initial ON cause.
- Native motion from device 7746 notified Shower app 4014; no observed command edge to Bathroom lights.
- Historical Journal device 7895 had 5 active receptions within ~0.7–1.3s *after* each target ON source report and five inactive receptions ~8.7–9.0s before OFF. These are collector-reception clock observations: cannot prove actual sensor-vs-light event order or initiating platform.
- Device 7754 had 160 archived motion receptions; returned query truncated, receipt capped at 20, compact full-page summary stored.
- No trustworthy command/execution trace of original ON issuer from Hubitat, Hue, HA or SmartThings. Current question remains unresolved.

**Critical code finding:** `unified_incident_synthesis.py::reconcile_ledger_if_needed` **always replaces the model's own narrative** with `source_incident_digest` when target histories are gapped and archive source switch rows exist. This may mask model reasoning quality and enforces repetitive static answers.

**Review request:**
1. Audit whether this is the biggest remaining architectural defect versus MCP evidence/tool discovery gaps.
2. Propose minimal typed evidence/claim witness contract and safe conditional publication rules.
3. Design dependency inversion and model-selected next-tool decisions with real Hubitat/HA/Hue source capabilities and no invented edges.
4. Explain which original command origin evidence is fundamentally missing, and how HomeBrain should tell users that rather than repeat reads.
5. Recommend stage-by-stage implementation priorities with concrete regression tests across two *different* incidents (Bathroom lights + Bedroom 3 Mesh offline).
6. Identify security, performance and reasoning risks. Challenge the current RFC where wrong.

**Important:** Do not assume the sensor caused the lights because of pattern coincidence; `producedBy` is not necessarily a command issuer; a lack of returned command rows is not proof no command existed; reception time is not source time; current app config is not an historical execution trace. No live Hubitat changes.

**Links:** [GitHub repository](https://github.com/ienam-smarthome/HomeBrainOS), [V3 RFC](RFC-CAUSAL-INVESTIGATOR-V3.md). Please inspect real source before giving code-level conclusions. Respond with: strongest and weakest design premises, top three concrete architectural changes, migration/test plan, and what NOT to build.
