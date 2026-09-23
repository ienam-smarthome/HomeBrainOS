# Hubitat MCP AI 0.16.19

## Compact mobile UI and complete device-inventory fast path

This release combines two user-facing improvements: a denser ingress dashboard
for phones/tablets and a deterministic whole-home device inventory path that
removes the slow model-driven pagination seen in the 0.16.18 live trace.

## Compact/mobile ingress UI

The dashboard now places both tile groups immediately below the title:

1. the four live summary tiles;
2. the quick-action strip.

The four live summary tiles are substantially smaller. On screens up to 520 px
wide they render in one four-column row and hide their secondary captions so
the current counts stay visible without consuming half the screen.

Quick actions render as six compact tiles:

- What's happening?
- Rules
- Hub health
- Firmware
- Refresh MCP
- Local backup

The following shortcuts were removed as requested:

- Open sensors
- Recommendations

The new **Local backup** tile opens:

```text
http://192.168.1.239/hub2/createFullLocalBackup
```

in a separate browser tab. It is a direct browser navigation link; the local
backup URL is not sent through the AI/model path.

The query/answer card, MCP status strip, and system-check card remain available
below the compact top tiles.

## Device inventory: observed 0.16.18 baseline

A live broad-device request on 0.16.18 returned only 150 of 191 devices and took
37.1 seconds.

Observed metrics:

```text
hub_list_devices page 0:    6.618 s
hub_list_devices page 50:   5.536 s
hub_list_devices page 100:  6.589 s

MCP HTTP:     19.1 s
Provider:     18.0 s
Model rounds: 4
Tool calls:   3
Total:        37.1 s
```

The model stopped after three 50-device pages, so the response was both slow
and incomplete.

## Deterministic device inventory

0.16.19 adds `homebrain_device_inventory`, a local read-only tool backed by
`HubitatMCPClient.get_device_identities()`.

For broad whole-home inventory prompts such as:

```text
list devices
show all devices
device inventory
what devices do I have?
```

HomeBrain now handles the request before capability search, system-prompt
construction, or a provider/model round.

The inventory path:

- reuses the fresh authoritative structural identity cache when available;
- otherwise prefers the one-shot `hubitat://context` resource;
- falls back to the existing detailed manifest only when the complete bulk
  context is unavailable;
- deduplicates by device ID;
- groups every returned device by room;
- sorts room names and labels deterministically;
- returns the complete inventory without model-authored category guesses.

The structural identity cache is valid for the configured identity TTL
(default 120 seconds), so routine dashboard activity can make subsequent
inventory requests fully local.

## Expected fast-path shape

A warm-cache inventory request is expected to have:

```text
model_rounds: 0
remote hub_list_devices page calls: 0
provider timing: absent
```

A cold request may need one bulk live-context refresh before rendering. This
release does not claim a live elapsed-time improvement until the updated add-on
is installed and retested against the real hub.

## Grounding

Device inventory is explicitly structural identity evidence, not live device
state. The evidence receipt therefore has `supports_live_claim=false`. Live
questions such as which devices are on, open, active, hot, or low-battery
continue to use the existing live-state tools instead.

## Regression coverage

0.16.19 adds tests for:

- complete room-grouped inventory from one identity read;
- deterministic inventory rendering without truncation;
- zero provider/model use for the supported broad inventory phrasings;
- no remote `hub_list_devices` pagination on the inventory fast path;
- inventory evidence marked as structural rather than a live-state claim;
- the expanded local-tool catalog;
- compact summary/action tiles appearing before the query card;
- mobile four-column summary and three-column quick-action layout;
- removal of Open sensors and Recommendations;
- the Local backup tile and exact Hubitat backup URL.
