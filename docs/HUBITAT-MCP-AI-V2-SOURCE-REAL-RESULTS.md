# HomeBrainOS v2 — First source-real receipt-review checkpoint

**Observed on:** 9 November 2026. **Status:** User-supplied first-answer Technical JSON packet, **receipt-reviewed, not independently verified against the live hub**. This is a source-quality checkpoint, not a release or proof of a reasoning improvement.

## Evidence custody and capture

Ten private v2 Ask Technical JSON exports were supplied externally and examined **off-repository**. They report the same add-on version **2.0.0-alpha.26**, the same configured model identity, ten distinct request identifiers, zero prior conversation receipts used, and ten `success: true` answers. The exported receipts contain **21 model-selected native MCP tool attempts**, of which **20 succeeded and one returned a server-side error**; 29 model rounds; and **no device-control calls**. Median browser elapsed time was **9.445 seconds**. These are descriptive measures, not factual-answer correctness.

**Safety limitation:** The hub-info read reports `writeEnabled: true`. This does not independently establish a particular token's permissions, but **a server-enforced read-only boundary was not demonstrated**. No write operations are visible in the ten submitted model-tool receipts. Before any further real-hub acceptance study, verify and enforce read-only access server-side; question wording is not a security control.

**Integrity limitation:** The uploads did **not** include the original locally sealed `frozen-questions.json` and SHA-256 file. The captured question wording matches the planned source-real categories, but the private manifest/seal integrity check **has not been performed by this review**. First-turn and source-real status are inferred only from supplied captures; the reviewer did not witness their execution or re-query the hub. Do not retrospectively manufacture a seal or mark provenance as independently verified. No raw household data, addresses, device identifiers, log text, model credentials or original exports are committed to the repository.

## Provisional answer/source findings

| Case | Receipt-bounded assessment | General weakness or supported behavior |
| --- | --- | --- |
| sr-01 — hub status | Source-supported | Uptime, memory and two observed temperatures supported by current metadata and metrics. No past data was projected into the present. |
| sr-02 — battery inventory | **Material error** | All 211 returned device entries were present, but **32** had battery values and **179** lacked values; the answer claimed 22/189. One server-side argument/format rejection occurred before correction. |
| sr-03 — brightness history | Partial | Only one level event returned under the default **24-hour** history query; the answer did not clearly qualify that earlier records might exist when asked for the latest three overall. |
| sr-04 — temperature history | Source-supported | Eleven returned readings were correctly described and missing interval behavior left unverified. |
| sr-05 — thermostat current state | Source-supported | Both requested devices and both requested attributes were observed in current-state snapshots. |
| sr-06 — reboot history | Partial | A firmware `update` event preceded a `systemStart` event. These strongly support association, but the response claimed the update was the **verified cause** without an independent restart mechanism/issuer. |
| sr-07 — automation configuration | Partial | The assistant-proposed controller name had no exact app match; a related humidity-control app was inspected. Its Unit 3 page supports the reported values but other related units/target identity were not checked. Do not silently equate a related app with the exact named automation. |
| sr-08 — energy history | Source-supported | Two cumulative kWh readings and timestamps supported; no fabricated instantaneous or continuous intervening power claims. |
| sr-09 — contact history | **Invalid evaluation target; partial answer** | The label suggested in the assistant's test setup resolved to a **motion-only** sensor, not a contact-capable device. The model noted the capability mismatch but still phrased no open event categorically. The intended contact-history capability was **not tested**. |
| sr-10 — diagnostics | **Material error** | Source returned **100 WARN rows out of 124 matches** and **11,477 total log entries**, not the complete warning/error picture. Query filtered WARN without checking ERROR; an app log asserting intention to initiate a reboot was treated as an accomplished reboot; retention/rotation explanations were speculative. |

**Provisional grouping:** Four source-supported responses, four partial/qualified (including the invalid target) and two material errors. This is **not** an independently adjudicated claim-by-claim grade; do not publish a generic first-answer success percentage from these classifications. The model's ten `success: true` flags reflect API completion only, not source correctness.

## Root-cause candidates and next gate

1. **Aggregation accuracy:** Numeric inventory summaries must be derived accurately from the records actually returned, including present/missing values and denominator.
2. **Scope awareness:** Models must not transform a limited history, filtered log page, incomplete inventory or adjacent event into universal absence or verified causation.
3. **Target identity:** A near-match app or a device with an incompatible capability must be explicitly surfaced, not silently substituted. Separate **test-design/assistant-suggested input** flaws from AI reasoning failures.
4. **Schema comprehension:** Observe and classify server schema errors separately from client contract rejections; build general semantic guidance around live server descriptions, not guessed fixed tool plans.
5. **Safety and study integrity:** Independently verify read-only permissions, compare the locally sealed manifest to source exports, and preserve original first answers. Do not grade this as a fully compliant read-only study without those prerequisites.

**Development decision:** Do **not** promote the previous generic synthetic prompt candidate or change production v2 from this small review. Do not retune to these ten exposed questions and call the resulting rerun an independent study. Keep model-led tool selection, upstream schema authority and v1/Hub Diagnostics unchanged. Record the data limitations, obtain an independent claim-level assessment privately, then define a **new unseen, permission-verified** prospective test for a general evidence sufficiency and schema-usage improvement.

## How to complete independent review privately

Run the existing offline `hubitat-mcp-ai-v2/tools/source_real_acceptance.py verify` against the **original** private frozen manifest and all ten unmodified Technical JSON exports; the reviewer supplies a separate private `homebrain-v2-source-real-human-review.v1` file using explicit verified factual-claim and unsupported definite-causal-claim counts. If the manifest or read-only permission cannot be verified, record the limitation instead of backfilling proof. Neither live device activity nor original private evidence should be uploaded to this repository.
