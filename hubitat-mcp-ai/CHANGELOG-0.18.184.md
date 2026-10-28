# HomeBrainOS 0.18.184 — Native agent entity lookup and source-quality improvements

## Evidence from 28 October live tests

Native hub-log audit (14.97s) successfully returned one ERROR and 100 WARN
entries, correctly identifying watchdog, Google Nest Hub load, SenseCap D1,
Iron socket and heating-scheduler warnings. Conclusions about system-wide
root causes were not independently established by performance metrics.

Bedroom 3 Mesh investigation (35.38s) got stuck: selected Hub Mesh (which
is hub-to-hub sharing, unrelated to the Tasmota device label), timed out
on unfiltered device inventory, and issued device-detail calls lacking a
valid deviceId, which failed before executing. The source-projection
fields for device health were also incomplete.

## General fixes

- The model is offered a new bounded, host-local, READ-only function
  `homebrain_find_device(name)`, returning only independently verified
  live identity matches. The model chooses when to invoke it; there is no
  question-word router or mandatory inventory fetch for hub-wide questions.
- Exact normalized name matches are allowed; only a unique anchored
  prefix may be promoted. Ambiguous, unknown or stale matches **never**
  authorise a targeted device call.
- Targeted MCP operations such as `hub_get_device` now reject missing
  required operation fields before calling ToolExecutor, with feedback
  telling the model to resolve the device first.
- The agent distinguishes Hub Mesh (hub-to-hub sharing) from a physical
  device with “Mesh” in its label.
- Device health and hub-sharing adapter projections now retain reviewed
  safe keys, such as staleDevices and unknownDevices, instead of silently
  discarding their values.
- Structured log source identity matching normalizes cosmetic punctuation,
  whitespace and case but still requires a matching name AND source type;
  this helps attest Nest Hub source IDs without accepting arbitrary
  IDs embedded in log text.
- Final AI Markdown retains paragraphs, headings and bullets without
  sacrificing bounded output and credential redaction.

## Regressions

Tests exercise model-driven identity lookup, source-grounded ID admission,
no full-device inventory for hub queries, ambiguity denial, operation
missing-field rejection, source-ID spoof rejection and preserved Markdown.

## Limits

This is NOT a claim that HomeBrain currently matches Claude on arbitrary
questions. Identity refresh may still encounter a slow or unavailable hub,
and the provider may make poor tool choices. A successful warning audit
does not prove the warned component is the primary cause of hub-wide
instability. Native V2 remains read-only and separate from production
Main Ask. Live acceptance against the actual user hub is required.
