# 0.18.38 — Collapsible Q&A history and consistent command provenance

## User-reported issues, 19 October 2026
HomeBrain 0.18.37 correctly captured a historical `command-off` on 12 October 2026 at 01:30:01 BST, produced by app 3950, and correctly marked command history checked. Nevertheless the model's final prose opened with "I could not verify the claim about [the named app]", while its own typed source metadata recorded `recordedCommandProvenance.commandRecorded=true`. Model performance improved to 25.1s compared to 43.9s, but it still used seven model rounds and ten read-only tool calls, including a noncontributory `hub_list_device_events` request with `appId` instead of an app-log read.

Meanwhile the user's saved Chats history displayed many fully expanded previous question-and-answer bubbles with lengthy answers, forcing the main ask box and latest answer far down the page. Previous restored chat answers also printed literal Markdown formatting markers, unlike the latest answer.

## UI: compact accessible conversations
- Each stored **Q&A pair** is one keyboard-accessible native `details/summary` accordion with the question as a one-line ellipsized heading. **All previous pairs start collapsed.** Tap/click any question to expand and see the saved answer, or collapse it again.
- Add **Collapse all** and **Expand all** to the Chats toolbar, covering previous pairs and the current response. The most recent new response is **expanded when returned**, but reopens **collapsed** when switching to a saved conversation or reopening the browser.
- Render historical answer content using the same DOM-based Markdown renderer as live replies (bold, numbered lists and scrollable tables) without evaluating untrusted HTML. No old write confirmation, action, or auto-speech controls are revived.
- Reuse the existing current-answer component inside an expandable `details` wrapper, retaining technical details and live action confirmations while expanded.
- Prune empty, never-answered New chat tabs when creating/opening conversations, so unused tabs stop filling the Chats strip.
- Preserve the current 20-conversation/32-message browser-local storage bounds, separate session IDs, current request abort guards, last-eight-message follow-up context, and Free-by-default model choice.

## Evidence consistency
- Preserve an optional source-observed command issuer name in `recordedCommandProvenance`, alongside the verified app ID and timestamp.
- When an existing successful, target-scoped, timestamped command record names the exact app that a model's boilerplate opening claims is "not verified", replace **only that contradictory denial** with a factually bounded positive command statement.
- Never promote a switch-state event to command proof; never verify the automation's triggering mechanism, MQTT delivery, physical acknowledgement or subsequent offline causality without independent evidence.
- Do not change causal source coverage, MCP permissions, model routing or write confirmations. A separate follow-up will target smarter app-log source selection and unnecessary model rounds.

## Tests
Regression coverage for both compact and expanded Q&A pairs, preserved Markdown, toolbar controls, legacy session/confirmation safeguards, no cross-session stale actions, empty-chat pruning, command denial corrected only for an exact same-turn matched app name and positive command evidence, and preservation of unrelated/model uncertainty. Node syntax and simple DOM-behaviour tests run in CI. Merge only after all three GitHub workflows pass; Home Assistant UI verification remains a live test.
