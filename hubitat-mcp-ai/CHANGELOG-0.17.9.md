# HomeBrain 0.17.9 — Causal claim integrity and UI readability

The live 0.17.8 deep investigation of a bathroom light at 07:53 correctly identified its direct app command and the likely occupancy sensor, but the model still promoted immediate command ownership into unsupported claims that manual input and other automations were entirely "ruled out." The previous single-format validator missed bold bullets, prose and the certainty-table cell. The response also called sensor device-history data "Hub logs" even though the targeted app log search returned zero entries and the separate broad log read contained no named occupancy-sensor event. Finally the HTML renderer displayed fourth-level Markdown headings and LaTeX arrows literally.

## Shared fixes

- **Causal exclusion integrity:** One evidence-backed guard checks all answer surfaces (prose, bullets and tables) for categorical manual/mode/other-automation exclusions that direct app ownership cannot prove. It preserves the verified immediate command producer and properly qualifies possible upstream initiators.
- **Source attribution:** Native log entries and correlated sensor event history are explicitly distinguished. Successful empty app logs or unrelated broad logs do not support claims that "Hub logs show" a named occupancy event.
- **Two answer boundaries:** The same generalized causal checks operate during model synthesis and in the post-synthesis API serializer, so a repair pass cannot silently reintroduce an unsupported exclusion.
- **HomeBrain web interface:** Markdown headings up to six hashes are rendered as headings; common math-arrow markup is displayed as readable arrows in paragraphs/tables and spoken naturally by the read-aloud feature. Rendering uses DOM text nodes rather than injecting raw HTML.
- **Regression tests:** Representative deep causal answer with bold list alternatives, inline exclusions, a false certainty-table status, empty scoped logs and unrelated broad logs. Also tests against a genuinely matching native sensor log, preservation of app provenance and UI renderer compatibility.

No control writes or Hubitat settings changes. This release strengthens the shared reasoning/output contract and presentation, not a Bathroom-only workaround.

## Known bounds

Command-producer metadata proves a specific device command's origin, not all prior manual/controller influences. A timestamp-aligned configured occupancy event is strong supporting evidence, but without a recorded internal app decision the exact activation path may still be classified as likely. Unobserved upstream causes remain unconfirmed. Live provider response quality requires installation and another trace.
