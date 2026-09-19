# Hubitat MCP AI 0.14.13

## TTS targeting diagnostics and trustworthy current time

- Improve Home Assistant Android TTS target selection when several
  `notify.mobile_app_*` services exist by matching the current Android/WebView
  device model (for example `SM-S938B` to
  `notify.mobile_app_sm_s938b`) before requiring manual configuration.
- Pass the current client user-agent into the native TTS resolver without
  persisting it.
- Replace the generic **TTS setup needed** button state with the precise backend
  failure reason, shortened for the button and retained in its tooltip.
- Preserve explicit `ha_tts_notify_service` as the highest-priority target.
- Route direct questions such as **What's the time?** through a deterministic
  hub-local clock instead of the language model.
- Resolve the authoritative Hubitat location timezone, then format the current
  clock time directly (for example `It's 6:06 PM BST.`).
- Keep unrelated historical or scheduled time questions out of the new
  current-time fast path.
- Add regression tests for S25-style device matching, client-hint forwarding,
  visible TTS errors, current-time intent classification, and hub-timezone
  presentation.
