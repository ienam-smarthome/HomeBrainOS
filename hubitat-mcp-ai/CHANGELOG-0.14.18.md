# Hubitat MCP AI 0.14.18

## Open HomeBrain in an external browser

- Add a compact **Open in browser** shortcut beside **Read answers aloud** when
  HomeBrain is running inside the Home Assistant Android WebView.
- Use Android's documented intent-link mechanism so the current Home Assistant
  HomeBrain panel is handed to the phone's external/default browser.
- Prefer the parent Home Assistant panel URL instead of exposing the raw ingress
  session path when that parent URL is available.
- Strip the Companion app's `external_auth` query flag before handing the URL
  to a normal browser.
- Keep the shortcut hidden in normal browsers, where browser speech already
  works and no extra control is needed.
- Preserve all existing Ask/Speak, TTS fallback, System Check, and Pushover
  behaviour.
