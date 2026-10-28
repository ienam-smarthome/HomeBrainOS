# HomeBrainOS v0.18.188 — Typed cross-domain command provenance

## Live evidence and architectural gap

The 28 October v0.18.187 Google Nest Hub investigation completed in 21.982 seconds with eight successful READs. It retrieved 71 WARN log rows for device 7934: 43 sampled runQ rows (reported 147,429ms), 27 excessive hub-load rows, and one setVolume row (124,842ms). These are returned log-row counts, not necessarily distinct invocations. The new device-event history also identified two command-issuing applications that the answer did not mention:

- App 4080 (00 Google Calendar Notifier) issued speak/setVolume commands.
- App 1679 (Adhan Player) issued repeated refresh/setVolume/playTrack commands.
- A setVolume command stamped 17:42:22.698 and a setVolume slow-method WARN stamped 17:42:22.697 have a one-millisecond **displayed wall-clock proximity**, but the log timezone and causal direction are not independently verified.

The old focused summariser discarded app-issued device-event records because their producedBy appId did not equal the target device ID. App IDs were also not attested as app identities, so hub_get_app_config and hub_get_source follow-up reads were refused. hub_list_device_dependents and hub_list_drivers returned successful results but their important relationship lists were discarded.

## General-purpose read-agent improvements

- Preserve **typed source provenance**. Approved, device-scoped event receipts now retain the issuing app's identity separately from device identity. A device ID cannot authorise app or driver source reads, and an app ID cannot masquerade as a driver ID. All calls still require the live READ manifest and existing tool schema and effect checks.
- Model-visible device-event evidence now prioritises app issuer IDs, command names, count and timestamps. It omits speech descriptions, reminders, media URLs and sensitive command arguments.
- Host evidence extracts independent source relationships from device dependents, driver catalogues and safe app-configuration metadata; the model selects any additional permitted reads.
- A general same-method timestamp comparison (not a question-specific rule) can flag a command and WARN with matching wall-clock time, explicitly marking timezone alignment and causality as unverified. It never infers an operation's start from its completion log.
- Focused source-first fallback cites calling apps and treats them as concrete investigative leads rather than asserting they caused driver stalls.
- Source read results that provide only code availability are explicitly labelled as metadata, not completed code analysis.
- The existing default Main Ask and automation/write paths remain unchanged.

## Safety, regression and remaining gaps

Tests cover distinct app/device/driver identities, ID spoofing, ambiguity, a model-led device-to-app investigation, read-only app source calls, chronological proximity, and redaction of speech/reminder text. Actual Google Nest Hub driver execution and impact on the hub remain unverified. A later stage must inspect source/driver control flow and independently validate material causal claims against evidence. The synthetic checks do not establish Claude-equivalent live accuracy.
