# 0.17.5 — Show seconds in concise causal lighting answers

HomeBrain 0.17.4 correctly connected Bathroom Light 1's 07:53:36 activation with a configured LWR01 Bathroom Occupancy motion event but collapsed all answer timestamps to whole minutes. This obscured event order: the sensor registered active at 07:53:36.542, the app sent setLevel(50) at 07:53:36.621 and the light reported ON at 07:53:36.721.

## Changes

- Show **HH:MM:SS** for observed ON, sensor activation, subsequent brightness changes and OFF, using the observed event's local timezone rather than converting local Hubitat event times to UTC.
- Keep subsecond timestamps and signed event differences in the structured investigation evidence; avoid exposing milliseconds in the simple user-facing answer.
- When a completed ON interval has a valid end boundary, include a human-readable elapsed duration (for example `17m 21s`); never invent an OFF event for an open interval.
- Improve short-answer flow: describe motion observations as motion, use direct “at” rather than “around” with a known sensor timestamp, and fix “the light went off” appearing lowercase at the start of a sentence.
- Keep the existing distinction between confirmed app commands and a **likely** sensor trigger. Event ordering alone is not definitive proof of the app's internal conditions.

## Regression coverage

Tests use the actual 12 October 2026 Bathroom event's switch/sensor timestamps and include elapsed-duration, timezone-equivalence, brightness adjustment and open-interval cases. The changes are presentation-only; no Hubitat commands or automation modifications are introduced.
