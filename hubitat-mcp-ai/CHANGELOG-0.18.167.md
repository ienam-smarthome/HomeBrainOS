# HomeBrainOS v0.18.167 — Attribute vocabulary vs device subject disambiguation

## Live failure investigated

The v0.18.166 read-only V2 test for:
“What is the current switch state of Hallway Light 1 and Livingroom Light 2?”
failed with HTTP 422. Although the correct full labels were in the live
inventory, the word “switch” before the first light label also matched
two unrelated sockets whose generic underlying driver name is “switch”:
LivCAM socket (#7786) and FP2 Livingroom socket (#7787).

The earlier ON command to Hallway Light 1 (#7829) was a separate,
correctly verified routine write and is unaffected by this read-only fix.

## Architectural change

- Resolve exact independently verified multiword device subjects first.
- Distinguish a read attribute qualifier (“switch state of Hallway Light 1”,
  “temperature reading of Hallway Light 1”) from a device name only when
  a narrow attribute + relation leads directly to that verified subject.
- Treat every other ambiguous earlier generic device mention as blocking.
  “Check the switch and Hallway Light 1” or “Is switch on?” must still
  refuse to guess which physical socket is intended.
- Never create IDs from the model, skip a live inventory safety check,
  or expand the request beyond the named subjects.
- Keep V2 strictly read-only. Routine device writes and their separate
  reconciliation/confirmation path remain unchanged.

## Tests

Synthetic inventory now reproduces the real #7786/#7787 generic-alias
collision alongside Hallway Light 1 (#7829) and Livingroom Light 2 (#7828).
Regression checks cover two-device read answers, incidental attribute
qualifiers, explicit generic alias ambiguity, and no extra devices.
The existing end-to-end V2 HTTP test therefore exercises the original
error shape with the duplicated generic alias.

## Live acceptance

After upgrading to 0.18.167, repeat:
“What is the current switch state of Hallway Light 1 and Livingroom
Light 2? Read both devices directly from Hubitat. Do not change anything.”

Expect only the two named lights and their respective current reported
switch values. Any live values may have changed since previous captures;
do not treat CI fixture values as current Hubitat readings.

The cold five-page inventory can still be slow; that is a separate
performance issue. No live Hubitat mutations were performed in development.
