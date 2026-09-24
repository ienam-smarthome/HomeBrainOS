# Hubitat MCP AI 0.16.29

## Room + device-kind recovery for natural plural history targets

A live 0.16.28 history request used the natural target:

```text
hallway lights
```

HomeBrain treated that phrase as a literal device label. The targeted lookup
returned zero rows, then the history fallback reduced the request to the generic
token `lights`, which also returned zero rows. The final answer was therefore
`device not found`.

That is incorrect when the authoritative Hubitat identity world contains real
light devices assigned to the Hallway room.

## Fix

0.16.29 adds a strict room + device-kind recovery step to named device
resolution.

A phrase is eligible only when:

- its final token is a known device-kind word such as light/lights,
  switch/switches, socket/sockets, plug/plugs, outlet/outlets, lamp/lamps,
  bulb/bulbs, sensor/sensors, or motion;
- the preceding text exactly matches an authoritative Hubitat room name;
- candidate devices actually match that device kind.

No fuzzy room matching is introduced.

## Multiple devices

When an exact room-kind reference identifies more than one device, HomeBrain
does not silently select one.

For the live Hallway shape:

```text
Hallway Light 1
Hallway Light 2
```

the resolver returns those concrete devices as alternatives.

The history service then reports an ambiguous target rather than incorrectly
claiming the device/group does not exist.

It also skips the old second targeted lookup for the generic token `lights`.

## Single device

If a room-kind phrase identifies exactly one device, the target can resolve
directly.

For example, if the Toilet room contains one light, `toilet lights` can resolve
to that light without requiring clarification.

## Scope and safety

This is identity resolution only.

0.16.29 does not:

- create a synthetic multi-device history object;
- merge two device event streams;
- guess which member of a multi-device room group the user intended;
- alter control-group semantics;
- change the 0.16.28 causal-correlation logic.

A multi-device room-kind history request therefore surfaces the concrete members
for clarification rather than inventing group causality.

## Regression coverage

Adds live-shape tests proving that:

- literal `hallway lights` label lookup may return zero;
- authoritative identity metadata still identifies the Hallway room;
- only light-kind devices from that exact room are selected;
- Hallway Meter and lights from other rooms are excluded;
- `Hallway Light 1` and `Hallway Light 2` are returned as alternatives;
- no second `labelFilter=lights` lookup occurs;
- no event history is read until a concrete member is selected;
- a single matching room light resolves directly;
- non-existent/fuzzy room phrases remain unresolved.
