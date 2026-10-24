# HomeBrainOS 0.18.90 — Application source investigation objective and evidence alignment

## Live regression (24 October 2026, 09:48 local log time)
A v0.18.89 read-only question about **installed App 3977** and its `setReportData` `LimitExceededException` retrieved Groovy code **1410** twice (two complete reads of **81,240/81,240 characters**) and queried App 3977 configuration plus app/device 7182 logs. The final response said the answer did not address method `body`, incorrectly recording `primaryObjective.method="body"`. It also required physical device state and device event history to complete an installed-app source-code analysis, even though current-turn app and device log queries completed and returned zero rows.

## Changes
- **One true method identifier:** `investigation_objective.requested_groovy_method_symbol` rejects generic grammatical nouns such as "method body", "method implementation", "method source"; selects explicit named or code-shaped identifiers (e.g. `setReportData`). Answer-focus checks reuse the **same parsed objective** instead of independently extracting a conflicting method name.
- **Correct runtime proof obligations:** A named installed-app source request checks read-only **app configuration and scope-matched app/device logs**, as requested. No default demand for the current state and physical event history of a device. Successful empty log pages remain bounded observations, never proof no exception occurred. Existing physical-device driver investigation requirements remain unchanged. Completion warnings now use correct app-versus-driver terminology.
- **Targeted no-tools AI repair:** If model synthesis fails to address the actual requested method or error, do at most **one** additional model-only repair from the existing tool evidence, without collecting new devices or rewriting as Rule Machine or full-hub performance. Rechecking focus does not establish correct Groovy semantics.
- **Per-request source-page read cache:** When the model asks to inspect a second symbol of the same app within one user request, reuse successful and byte-identical MCP source pages and read-only metadata within that request; re-evaluate method excerpts for the newly requested symbol. Discard cache at request end; no writes and no cross-session/cross-request carry-over.
- A named-method excerpt obligation is enforced **only for actual explicit method identifiers**, not the generic noun `body`. Verified full-file reads remain different from verified balanced method excerpts and from verified runtime causation.

## Tests
Regression suite covers the exact App 3977 phrasing, method identifier, zero-row scoped logs, missing target logs, method excerpt uncertainty, one-round focus repair, request-local cache isolation, no cache of failed reads or writes, and existing architecture compatibility.

## Limitations
This release removes the observed false evidence requirements and repeated raw source downloads, but is **not** proof that Gemma has already diagnosed App 3977 correctly. The true cause of prior `LimitExceededException` events still needs actual `setReportData` body/caller details and source-linked dated execution evidence. No Hubitat device, rule, app, live configuration or paid model option has been changed.
