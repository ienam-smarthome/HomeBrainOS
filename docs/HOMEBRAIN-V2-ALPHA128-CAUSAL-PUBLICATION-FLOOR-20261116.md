# HomeBrainOS V2 alpha.128 — causal publication floor and inventory context

**Status:** candidate. V2 Preview only; no V1, smart-home scheduler, device, native action policy or approval changes. Installed acceptance remains **unmeasured**.

## Evidence from three PRIVATE installed alpha.127 read-only first answers

The model completed all three answers without the emergency alpha.127 empty-answer fallback, but the human source-real evaluations remained failed. It repeatedly equated reported setpoint changes with event-specific controller decisions, misordered a close group of observations, and in the most costly case scanned numerous zone histories without reading the shared controlled output before denying the earlier event. An app-ID filter on a device-event source was mistaken for meaningful application execution evidence. The full source-real first-answer quality and efficiency have not been fixed by alpha.127's completion fallback. Raw personal/home source receipts are **not** committed.

## General changes

1. **Read-only causal publication floor.** In the existing final-answer path, test a narrow class of unqualified global event-denials or definite internal-controller causal assertions against the ORIGINAL successful current-request source categories. A device event attribute producer or a setpoint/time pairing does not establish a controller's event-time decision. If the model asserts a cause but did not read an actual nonempty app/controller execution log, it cannot publish that unsupported definite conclusion. If it asserts historical absence without complete proof, it cannot publish that either. Instead retain a bounded **source-only partial** result from valid, already-retrieved positive device-state reports. Mark `causal_claim_verification`, `answer_fallback_status=causal_claim_publication_floor` and `response_success_scope` as partial. The floor is deliberately conservative; it does not try to prove that a returned execution log is correct, infer a focal target, or fabricate causal certainty.
2. **Smaller model input for broad causal inventories.** When the model chooses a large `hub_list_devices` summary in a read-only causal investigation, send it an identity-preserving current-state navigation INDEX with all returned IDs, labels and rooms, and selected small current-state fields. Keep the original full redacted native receipt in PRIVATE Technical JSON. No model-selected source, hub query, device identity, command, tool schema or action safety gate is changed. Noncausal inventory and small/invalid inventories remain intact.
3. **Better source type guidance.** Explicitly distinguish shared controlled outputs versus participating input devices; app-ID filtered device events are NOT an app execution-log read. A successful empty device event query does not establish an empty app log, and repeated overlapping reads are not an answer.
4. **Cross-domain fictional regressions.** Verify categorical denial, unsupported attributed cause, appropriately scoped/uncertain answers, app-event versus true app-log type, all inventory identities preserved, model context reduction, immutable original receipts, unchanged native call count and explicit partial metadata.

## Safety limits and live acceptance

The floor does not replace the model's actual investigation, does not pick/force a tool, and never applies to an explicit modifying device request or native action path. It is an additional guard against publishing a severely unsupported conclusion, **not** an 8/8 causal answer. It cannot prove that a real-world system operated or that an internal decision occurred. It may conservatively publish a partial result even when source reasoning beyond its fixed source-category check could establish a cause. Improvement in first-answer quality, genuine app-log discovery, model rounds, tokens, and response time must be validated in a NEW installed, uncoached source-real investigation. Do not imply CI proves those outcomes.

Use original read receipts to measure controlled-output history, event-time source selection, command issuer versus event decision, bounded chronology, fallback activation, source failures and model input reduction. Do not publish private household logs or claim independent physical evidence.

## Source frontier addition after upstream contract review

The connected upstream MCP project documents `hub_get_logs` with
`mode=past`, `appId` and a time window, as distinct from
`hub_list_device_events(appId=...)` which returns app-emitted events.
Availability still depends on the installed server's actual live catalog
and access policy; this PR does not call a live hub or force either read.

The existing causal controller-decision frontier now indexes bounded
**app-producer IDs from original non-command device state rows** separately
from genuine `command-*` issuer rows and `triggered[]` listeners.
An original app-produced state is a *candidate investigative lead*, not
verified command issuance or event-specific decision. In the existing model
source-review turn, the checkpoint can invite a model-selected targeted
past-log or event-time input read even if no command row was returned.
Successful read attempts are counted independently for reporter-app
candidates, and empty/failed app-log reads do not prove no execution.
No extra model round or host-selected tool/target is introduced.

Additional fictional regressions cover reporter versus issuer,
event-app versus native past-log source type, unrelated/empty/failed log
requests, broad categorical denials, short uncertainty caveats and
cross-domain source safety. The published claim floor only checks
necessary source-category coverage; it cannot certify that a log's
contents really prove the decision. No source-real model result is claimed.

