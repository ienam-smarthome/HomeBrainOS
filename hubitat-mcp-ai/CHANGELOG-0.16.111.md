# Hubitat MCP AI 0.16.111

## Deterministic `this afternoon` history window

- Recognises `this afternoon` in the original user request and binds it to the request-scoped semantic history context before model tool selection.
- Resolves `this afternoon` as 12:00–18:00 in the authoritative Hubitat local timezone, capped at the current time while the window is still in progress.
- Anchors explicit clock ranges such as `between 1pm and 3pm this afternoon` to today.
- Prevents rolling `hours_back` history from being labelled `this afternoon` while including pre-noon sessions.
- Adds an integration regression for the live Bathroom Light shape: the 11:28 am pair is excluded while the 1:17 pm and 2:47 pm intervals remain.
- Preserves the existing history presentation, retained-page completeness, source-integrity, and duration arithmetic behavior.
