# Hubitat MCP AI v0.18.350 — cross-source focal event reconciliation

## Actual production evidence: first-shot v0.18.348 Dehumidifier 1

The read-only case returned after **56.657 seconds / 11 Gemma rounds / 14 tools**. Native source-scoped Hubitat event history for device 5313 contained **command-off at 18:07:35.001Z from app 3995**, followed by switch off report at 18:07:35.273Z. An independent later command-on-only history read had the earlier app-issued ON at 16:31:23.210Z; switch ON at 16:31:23.288Z. The model ignored the earlier mixed-history OFF and asserted no recorded OFF command. It also miscomputed the ≈1h36 switch interval as **3.5h**, and claimed physical dehumidifier operation started exactly at first returned 88W sample (18:07:08), even though native 16-row mixed history was **truncated** and earlier power/current events may be missing. The recorded 0W→88W→81W→0W samples at 18:07:06 / 18:07:08 / 18:07:36 / 18:07:38 cannot establish full physical run time.

**Assessment: factual contradiction / unsupported hardware-operation claims — FAIL.** Source selection had succeeded; the defect was reconciling positive source evidence before final prose, not an absent device or yet another special-case domain template.

## Generalized source reconciliation

- Pure, request-local `focal_event_reconciliation.py` combines **only** successful nonmutating native device-ID-scoped Hubitat event pages and correctly label-scoped deterministic history for one independently verified target ID+label.
- Accepts both native `details.observedEvents` and filtered `details.events` source formats, de-duplicates timestamped switch / measured power / typed command events, and retains the issuing app only when positively marked as app via `producedBy.type=app` or explicit `producedBy.appId`.
- Computes latest bounded ON→OFF **reported switch-state interval** from two source-timed switch reports; never relabels it physical compressor/runtime. Projects discrete power readings as such, not exhaustive telemetry. Preserve `truncatedSourceObserved` and `sourceHistoryComplete=false` throughout.
- Appends compact canonical evidence packet **after** narrower historical source packets in the existing final model synthesis, so a last command-on-only read cannot negate an earlier command-off witness. Exposes same packet under `reconciledFocalEventEvidence` in Technical JSON.
- No extra model or MCP calls, no host replacement of natural model prose, no device/automation write privileges, no broad unread data retrieval.

## Validation and next step

Offline synthetic replay tests cover actual 272ms command-before-report pattern, both command directions, discrete power samples, truncated pages, ambiguous/wrong device ID, invalid clocks and app actor typing. Code/release/container/full Python CI must all be green before merge. **No live Hubitat/HA changes**. Runtime accuracy improvement and Claude parity are not yet measured; the longer-term goal remains one evidence-first source planning and completion engine rather than continued small per-event patches.
