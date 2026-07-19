# Hubitat MCP AI

Hubitat MCP AI is a hybrid local and Cloud assistant for selected Hubitat devices through the MCP Rule Server.

## HomeBrain Control Agent

Control Agent v1 separates language understanding from device execution:

```text
Request
→ local structured ControlIntent
→ deterministic selected-device graph
→ confidence and risk policy
→ fresh MCP command
→ Hubitat state verification
```

The local intent model receives no MCP command tools. It describes the requested action, room, device type, ordinal, group, exclusions and conversation reference. Python resolves those fields to selected Hubitat device IDs and applies the control safety policy. Cloud does not select device IDs, send commands or verify success.

### Direct controls

Exact low-risk controls remain deterministic and fast:

```text
turn off Livingroom Light 2
turn on Fan Boost
set Bedroom 1 Light to 30%
```

Contextual or grouped controls use the local structured interpreter:

```text
switch the second living-room light off
turn off all bedroom lights except the floor lamp
turn it back on
turn off the other one
switch both of them on
```

HomeBrain resolves every requested target before sending the first command. If one target is unresolved, no group command is started.

### Confirmation policy

Unique low-risk controls can execute automatically. HomeBrain asks for confirmation when:

- the target remains ambiguous;
- a sensitive device type is involved;
- the plan affects a large group;
- intent or resolution confidence is below the automatic-execution threshold.

Reply **Yes** to an exact proposed plan, **No** to cancel, or use the displayed number when HomeBrain asks you to choose between devices. No command is sent while a choice is pending.

### Learned aliases

Aliases are explicit and stored in the add-on data directory:

```text
remember "big light" means "My Floor Lamp"
turn off big light
forget alias big light
```

An alias is saved only when the destination resolves to exactly one currently selected device. It does not rename the Hubitat device and can be removed at any time.

### Control Agent options

- **Control agent enabled**: turns the new control pipeline on or off.
- **Intent timeout**: maximum local interpretation time for contextual controls.
- **Auto-execute confidence**: minimum confidence for automatic low-risk execution.
- **Block-below confidence**: plans below this threshold send no commands.
- **Group confirmation size**: plans at or above this device count require confirmation.

The existing deterministic control path remains underneath Control Agent and performs fresh command verification.

## Updating the add-on

Home Assistant normally detects a newer release after the custom repository refreshes.

If the release notes show a newer version but **Installed version** and **Latest version** remain identical, Home Assistant is displaying stale Supervisor store metadata. Restarting this add-on does not refresh repository metadata.

From the Home Assistant Terminal, run:

```text
ha supervisor reload
```

Then open **Settings → Apps → App store**, select the three-dot menu, choose **Check for updates**, and refresh the browser page.

If it is still stale, open **Settings → System → Logs**, select **Supervisor**, and check for repository validation or clone errors.

## Device catalogue refresh

After changing the selected devices in the Hubitat MCP Rule Server, open the Hubitat MCP AI web interface and use **Refresh Hubitat devices**. This clears shared device-state caches, reloads selected-device membership and detailed metadata, and invalidates dashboard counters.
