# HomeBrainOS 0.18.106 — Preserve evidence tables during causal claim corrections

## Live observation

The 24 October Livingroom Light 1 investigation (device 7805) used 19 recorded tool receipts and six free Gemma rounds (~54 seconds), including source device events, button history, two app-config reads and general motion/log/context queries. It correctly identified a button-1 command preceding the final ON transition and several actual commands from app 4019. It nevertheless reported an unverified "ghost motion" hypothesis too confidently, missed one completed ~8-minute ON interval in its text, and produced a broken Markdown timeline: the downstream-listener causality guard replaced an entire four-column table row with a prose qualification. The synthesis repair still failed.

## Focused fix

Change guard_triggered_listener_causal_claim to preserve all factual Markdown table columns (start, end, duration) while replacing **only the causal-attribution cell** when an event's triggered[] app was wrongly portrayed as initiating the state transition. Retain the bridge-producedBy versus downstream-listener distinction. Unsupported or nonstandard table shapes are left intact rather than overwritten. Existing narrative prose correction remains.

Add mocked historical Hubitat evidence tests covering a causal four-column table, an adjacent already-uncertain row, ordinary prose correction, an unaffected noncausal row and short malformed table preservation.

## Still to improve

This release fixes the *formatting integrity* bug, not the broader investigation completeness. The app 4019 off commands and button-1 ON provenance are recorded in the uploaded events; an ON duration alone cannot prove the historic motion sensor was false or stuck. App configuration receipts in the technical JSON do not include source details, and target-scoped time-bounded sensor states/app execution logs were not established. A future evidence-driven answer should separate what was observed from which mechanism is inferred, not invent source class completeness. No live devices or Hubitat automations were changed.
