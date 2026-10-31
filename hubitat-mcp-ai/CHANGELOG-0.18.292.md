# HomeBrainOS v0.18.292 — in-app Ollama Cloud benchmark (Stage 4N)

**User-facing addition:** A mobile-friendly "Ollama Cloud benchmark" section in the existing HomeBrain dashboard. The benchmark uses the configured **primary** direct Ollama Cloud API key, model name and shared ChatTransport HTTP client. No new Ollama account, token, GitHub secret, PC or GitHub Actions dispatch is needed.

## Using it
1. Update the Hubitat MCP AI add-on to v0.18.292, then open its web UI in Home Assistant or your phone browser.
2. Expand **Ollama Cloud benchmark**, choose Lighting, Heating, Ventilation or Missing contact history.
3. Read the cloud-allowance consent text, tick the checkbox, and click **Run one cloud test**. Each click authorises only one request. The checkbox clears after the result.
4. Read the model's explanation, elapsed time, correct/total predefined evidence judgments and the number of unsupported conclusions it incorrectly accepted. Expand the claim table for exact expected versus model-selected judgments.

## Safety and interpretation
- Every fixture is constructed, bounded, and fictional. No real device, history, log, prompt, account key or hub credential is part of the benchmark prompt. The four scenarios use canonical Stage 4A source packets and withhold their predetermined expected verdict labels from the model.
- The benchmark deliberately bypasses agent tools and local/paid/household failover routing. It sends **one** direct provider request through the existing primary Ollama Cloud credential and model to the official `https://ollama.com` endpoint only.
- It makes **no MCP calls**, home-device commands, Home Assistant services, file persistence or automation changes. The production model selector and V3 answer publication remain unchanged.
- It requires a same-origin dashboard POST carrying an explicit custom header, JSON body and true consent field. Browser requests made from cross-site origins are rejected. One call runs at a time, with a 10-second cooldown and maximum eight attempted calls in any in-memory hour. Provider failure or malformed JSON is returned as a generic error without sensitive details and is never automatically retried.
- Provider inference may use the existing Ollama allowance or credits. The benchmark isn't a read-only *financial* operation.
- **Scope of accuracy:** the numerical score measures classification of sixteen **predefined synthetic assertions** across four scenarios (four per run). It does **not** prove the natural-language explanation is fully factual, that causal investigation can find the right evidence, that all implicit claims were extracted, or that HomeBrain's publisher can be replaced. The model-written paragraph is shown for manual review but is not machine-certified.
- This version does not persist past results; the page displays only the most recent response during the browser session. No benchmark model prose is uploaded to GitHub or saved as a long-term record.

## Verification
New `tests/test_stage4n_inapp_cloud_benchmark.py` covers consent, same-origin request checks, no tool calls, source packet isolation, synthetic evidence classification, false-accept counting, HTTP-model error masking, cooldown, hourly cap, and user interface wiring. All standard CI gates must pass at the final PR head before merge.

Rollback: revert the single Stage 4N PR and restore v0.18.291. Existing agent, MCP and publisher behaviours are unaffected by the feature when not selected.
