# HomeBrainOS 0.18.120 — Evidence-led diagnosis and target fidelity

## Problem observed

A read-only user question asking **why** a controller sometimes kept a light on was reclassified as existing-rule verification. Despite collecting 42 read-tool receipts, the visible response became a lengthy certification checklist instead of addressing the most supported explanation. Optional Groovy code investigation also visited a different app instance without documenting its relevance to the investigated controller.

## General improvements

- **One semantic answer goal, independent of entity class.** The existing bounded no-tools AI interpreter identifies the requested deliverable (diagnosis, configuration verification, event trace, code inspection, status, inventory/report or design) separately from the type of entity. A diagnosis that inspects existing-rule configuration is still a diagnosis. A genuine request to verify stored rule actions retains the strict existing-rule contract.
- **Source target fidelity.** During a multi-round read-only investigation, once the host has retained an ID-matched typed rule/app receipt, a model-requested Groovy workbench read targeting a different app ID is rejected unless the user explicitly named it. The rejection is advisory; the agent can first establish a verified relation using its live read-only MCP tools. It does not authorize any writes.
- **Evidence-chain instruction.** The model must compare successful and failed episodes, check relevant controller settings/source/inputs and historical events, and stop when no accessible discriminator remains. Normal observed OFF timing is not proof of what happened on earlier exceptional nights.
- **Presentation.** Keep the requested supported answer ahead of incomplete provenance metadata; retain uncertainty rather than turning every causal question into an audit or claiming a proven root cause.

## Tests and limitations

New regression tests simulate contradictory entity/objective classifications, genuine configuration verification, backwards-compatible model replies, exact-ID source mismatch, deliberate multi-app comparison, and unverified source targets. No live Hubitat devices, settings or automations are modified. A green CI run validates contracts and integration but cannot independently guarantee the Ollama model will reproduce Claude's complete historical investigation; test against fresh Hubitat evidence after installing.
