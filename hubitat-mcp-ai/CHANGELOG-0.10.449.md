# Hubitat MCP AI 0.10.449

- Remove the hidden post-synthesis complete-device-manifest refresh from named-device claim grounding. The final grounding pass now uses request-local id/label pairs already present in structured tool results plus any detailed manifest that is already cached.
- Preserve the deterministic device-mismatch retry/refusal guard without adding Hubitat I/O after the model has produced its answer.
- Add bounded extraction of device identities from tool messages, ignoring naked ids, generic event names, malformed JSON, and duplicate identities.
- Add integration coverage proving final device grounding does not call `get_cached_devices()` for either ordinary device reads or history synthesis, including the Big lamp history path.
- Keep exhaustive inventory reads available to the workflows that genuinely require them; this change only removes the auxiliary final-answer refresh.
