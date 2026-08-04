# Hubitat MCP AI 0.10.322

Live-soak correctness fixes:

- route routine light and switch controls through the deterministic local control adapter before model tool selection, preserving literal user targets and returning ambiguity choices instead of silently choosing one device;
- answer exact last-open/last-close questions from the newest matching contact event in a bounded seven-day history window;
- retain unresolved device choices per browser session so pronoun-only follow-ups repeat the available devices and remain `unresolved` rather than becoming a grounding refusal;
- add focused regression tests for contact-intent parsing and clarification follow-ups.

No confirmation policy, sensitive-write handling, transport, or grounding safety rules are relaxed.
