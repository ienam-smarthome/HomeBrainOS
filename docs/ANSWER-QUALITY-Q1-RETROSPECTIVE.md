# Q1 retrospective — evidence of failure, not an acceptance score

**Date:** 2026-11-01  
**Purpose:** Preserve real source-grounded failure patterns for the fixed answer-quality programme without publishing household-private tool payloads.

**Interpretation:** These are **historical, differently prompted/retained app incidents**. Do not present them as a fair same-input A/B, as a full benchmark score, or as proof that v0.18.330 fixed the issue.

## Observed incident A — overly confident upstream trigger

- Recorded route: `unified-mcp-agent`, free Ollama Cloud `gemma4:31b`.
- Reported HomeBrain version: **0.18.328**. Reported elapsed time: **41.630 seconds**; tool calls **14**; model rounds **10**.
- The answer identified a recorded app issuer and a configuration/source-code branch consistent with an inactivity timeout, then asserted **high-confidence causation** and called the investigation complete.
- The same request's coverage packet had **all three hypothesis discriminators unverified**, `rootCauseVerified=null`, and no focal motion decision log. Verified command issuer ≠ verified upstream timer decision.
- **Review observation:** causal certainty exceeded evidence. This motivated v0.18.329, but does **not** by itself prove that later builds behave better.
- No original private event data, raw Groovy source, IP address, personal household identities or model answer is copied into this public document.

## Observed incident B — unsupported heartbeat hypothesis

- Recorded route: `unified-mcp-agent`, free Ollama Cloud `gemma4:31b`.
- Reported HomeBrain version: **0.18.329**. Reported elapsed time: **48.335 seconds**; tool calls **20**; model rounds **10**.
- The answer called a periodic `keep-off` mechanism likely based on a bounded historical window without motion records. However, the same broad supplied evidence included four later motion-inactive → recorded app-OFF command pairs at source-reported delays of **15.067, 15.100, 15.095 and 15.112 seconds**.
- The original focal OFF at **15:29** had no independently verified incident-time motion trigger. Positive later episodes support an inactivity mechanism for *those episodes* but do not establish the old focal cause.
- The periodic hypothesis had **no verified periodic scheduler configuration/decision provenance**; recorded command spacing was variable.
- **Review observation:** missed positive cross-source evidence and promoted an unverified alternative.
- This motivated v0.18.330's cross-source temporal evidence projection. The newer version **requires its own live acceptance**, not assumed success.

## Why these are not benchmark pass/fail results

- The two prompts and evidence sets were not proven identical.
- They originated from different add-on builds.
- The evaluation packet was not collected under a frozen prompt and fixed evidence replay.
- These examples do not constitute 31 graded cases or a Claude comparison.
- No production v0.18.330 answer capture has been received for the fixed Q1 prompt yet.

## Reproducible next step

Run the existing registered **`causal_light2_off`** first-attempt prompt *without modification* on current v0.18.330:

> Investigate why Livingroom Light 2 turned OFF most recently. Do not change anything.

Provide the complete natural-language HomeBrain result and technical JSON. Verify actual device/command evidence; do not assume history completeness. The Q1 capture CLI can extract a private metadata packet; manually review the answer against the source receipts, then record a real score for the specific model/build only when enough information exists.

**No device change is required.** If exact prompt evidence is missing, mark evaluation `unresolved` rather than grant fictitious success.
