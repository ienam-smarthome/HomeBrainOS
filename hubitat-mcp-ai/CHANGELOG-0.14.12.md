# Hubitat MCP AI 0.14.12

## Reliable answer speech in the Home Assistant Android app

- Add Home Assistant Core API access for companion-app native Text To Speech.
- Add a bounded `/api/tts` endpoint that sends `message: TTS` with
  `tts_text` to a configured Android `notify.mobile_app_*` service.
- Add `/api/tts/stop` using the companion app's `command_stop_tts` command.
- Prefer Home Assistant native TTS inside Android WebView / the Home Assistant
  companion app, where browser Web Speech synthesis is unreliable.
- In normal browsers, keep browser speech first and fall back to native
  Home Assistant TTS when speech fails to start.
- Auto-discover the target when Home Assistant exposes exactly one
  `notify.mobile_app_*` service. If several exist, require the explicit
  `ha_tts_notify_service` option instead of guessing.
- Surface a visible **TTS setup needed** state instead of silently doing
  nothing when neither speech path is usable.
- Add optional `ha_tts_media_stream` support for Android companion-app stream
  selection.
- Add service, endpoint, auto-discovery, stop-command, and WebUI regression
  tests.
