# HomeBrainOS V2 alpha.133 — remove duplicate Device overview

**Status:** PR candidate; require exact-head CI before merge.

## User-facing change

In alpha.132, System Health presented the same snapshot twice: one expanded
"Device overview · counts, names and refresh" panel, followed by "Needs
attention" and "Currently reported" cards with those same counts, names and
attribute coverage. The duplicate panel took substantial mobile/desktop
space and confused which surface should be used. Alpha.133 removes its
markup and dedicated duplicate DOM renderer.

Keep a single System Health source-backed summary:
- **HomeBrainOS runtime**: existing cached application/recorder/monitor cards.
- **Needs attention**: low battery, contacts, water, explicitly reported
  offline, and no reported activity for over 24 hours.
- **Currently reported**: identified lights on, active motion, reported
  thermostat heating states and other switches on.
- Each card's bounded names can still be expanded without another source
  query or AI request.
- **Snapshot coverage** still displays the number of devices inspected,
  declared inventory count and source limitations, instead of losing the
  important 203/203-style coverage context.
- **Refresh devices** moves into the main System Health header and remains
  a deliberate single read-only `/api/overview` request. The UI displays
  the snapshot time and identifies unclassified ON switches beneath the
  coverage summary. Failed refreshes invalidate stale card data and labels.

## Scope and safety

No backend inventory metrics changed, no live hub reads during tests, no
model call/prompt, no added scanning, no new polling, no device write,
no V1 code, no heating scheduler changes, no approval or write-safety change.
Existing `/api/status` and `/api/overview` contracts remain intact.
The Ask status popover now derives the device count from the cached original
inventory rather than a removed hidden UI node.

Updated Python structural contracts, Node UI tests, Chromium browser smoke
and screenshot contrast selectors to assert the removed panel stays removed
while manual refresh, names, error clearing, read-only source count and
model-cost behaviour survive.

**Installed alpha.133 acceptance remains outstanding.** After deploying
V2 Preview, check the single System Health page; expand "Low batteries"
and "Lights ON" names; verify "Refresh devices" updates snapshot time
with exactly one new read-only inventory request, without any AI charge.
