# HomeBrainOS v0.18.76 — Read-only multiline Rule Machine editor parsing

## Live observation
On 23 October 2026, v0.18.75 accessed app 4246 `selectActions`, reporting eight paragraphs with two multiline paragraphs, one paragraph over 400 characters, and presence hints for Cancel Delayed Actions, IF, END-IF, Delay and OFF. It recognized zero action rows. The previous parser rejected **any** paragraph with newline characters or more than 400 characters, so actual structured physical lines could be discarded.

## Change
- Split bounded editor paragraphs into physical lines and apply the **existing anchored** allowlist classifier to individual lines. This can recognize multiple displayed action rows inside a single paragraph, even if the entire paragraph is longer than 400 characters.
- For multiline text, require at least two separate anchored action lines before retaining any action tokens. A lone action-looking line followed by arbitrary text remains unverified.
- Limit source paragraphs to 8192 characters, 32 physical lines per paragraph and at most 40 emitted action records per page; mark page evidence truncated when bounds prevent complete observation.
- Retain only deidentified action names and numeric delay information, plus bounded physical-line/multiline counts. No raw editor text, names, conditions, settings, credentials, or URLs are declassified.
- Keep `orderedActionsValidated=false`, `conditionsValidated=false` and `investigation_coverage.stored_logic=checked-unverified` until an authoritative compiled Rule Machine action tree is available.
- Add regression tests based on the **shape** (8 paragraphs, 2 multiline, 1 oversized) of the actual app 4246 response. The content is synthetic because real raw paragraph values were not retained.

## Safety
This is an evidence-observability change only. It does not create, alter, disable, or execute Hubitat rules/devices. A collection of recognized editor rows does **not** verify that they are compiled or pending runtime actions.
