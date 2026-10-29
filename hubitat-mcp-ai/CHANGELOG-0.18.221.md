# Hubitat MCP AI v0.18.221 — Verified room membership and natural-language V2 answers

## Why

The 29 October Bathroom investigation demonstrated that complete device-state evidence was still presented in technical, attribute-oriented language, and a name-only group could miss a light assigned to the room (Shower Light). The display was also showing literal Markdown markup instead of visually formatted prose.

## Changes

- Native V2 retains model-selected, read-only MCP tool usage. The model can choose a live `hub_read_rooms / hub_get_room` read when a room matters. Only an independently name-matched returned room inventory authorises its member IDs for *subsequent, separately guarded* device reads. No whole-device inventory or hidden write is introduced.
- The response distinguishes **name-matched devices** from devices *actually assigned* to a room. A reported room member such as Shower Light is included with its current state only after an individual ID-matched `hub_get_device` read. If it was not read, V2 says so instead of guessing.
- User-facing group answers use natural English such as **“Bathroom Light 1 and Bathroom Light 2 are both off”**, followed by short device summaries. Stored dimmer levels are explicitly distinguished from illumination.
- The V2 test page safely renders bold lead statements, paragraphs and bullet lists; it does not trust model/source text as HTML. Raw answer text remains copyable, and the original technical report and read receipts remain available separately.
- Independent room-source verification, incomplete member lists and case mismatches cannot establish full room coverage. A complete verified group can skip unnecessary final claim-selection inference only when no independently returned room member is still unread.

## Verification

Regression tests cover name-vs-room distinctions, a room-only light, unread members, source identity mismatch, and preservation of read-only execution. No live Hubitat action is performed by the implementation. Production Main Ask is unchanged.

## Limits

An identity-matched room listing proves Hubitat-reported membership, not physical device operation. A room inventory is only classified complete when its returned member count agrees with the explicit `deviceCount` metadata. Model selection of the appropriate room read is still being evaluated with live prompts. No universal verification of unrestricted model prose is claimed.
