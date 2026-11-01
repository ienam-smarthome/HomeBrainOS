# v0.18.323 — Stage 8.8 evidence-first historical investigation brief

## Confirmed limitation
The prior real Historical Shadow run found six older switch-state observations collected retrospectively through native-history read-through, zero archived app-identifiable command records and substantial source/receipt-time differences. Command Shadow independently received zero raw source-event rows for the old selected day. None of these observations establishes the plug's physical switch actuation, exact connectivity-loss instant or initiating automation.

## Implementation
- Render **a source-bounded natural-language investigation brief before the verbose raw source audit** on the existing Historical Shadow screen.
- The brief uses only already-sanitized local-journal projection fields. It reports observed-state counts, command counts, a latest declared source-timed *report* (not the last physical event), retrospective native-history origin, apparent late source/receipt separation, collector gaps and potential page truncation.
- Explicitly state that no issuing-app command in a bounded archive page **does not** prove none was issued, and that a journal receipt date is not contemporary physical device contact.
- Explain that the root cause remains unresolved until independent contemporaneous app/command evidence and, for physical execution, a command-correlated acknowledgement is available. Do not suggest endlessly repeating an unchanged empty history query.
- Keep detailed event rows and timestamp/coverage diagnostics below the explanation for independent review.
- The brief does not combine source records from other screens or claim to check any unavailable logs. It does not cache private household logs or persist personal information.
- Strict safety flags: no authenticated clock, complete history, physical proof, causal promotion or production publication. No additional Hubitat or local journal reads, Cloud inference or device commands.
- Synthetic CI tests cover no command evidence, source-identified commands, delayed read-through, empty source page, collector gaps, 50-row cap, privacy and unchanged publisher.

## Mobile acceptance
Update to v0.18.323, open Live Shadow, enter device ID 7103, tick fresh **Local Journal** consent and select **Inspect archived device events (30 days)**. At the top of the returned result, inspect **Investigation brief · local archive only** before the technical audit. Its conclusion must keep the historical initiator and physical cause explicitly unresolved.

## Next architectural step
Do not add another historical retry against an already-empty source. For future incidents, use a separately authorised, narrowly scoped app-decision journal and command-identity correlation, observing existing retention and collection gaps. No capture settings are changed by this release.