# Hubitat MCP AI

Hubitat MCP AI is a hybrid local and Cloud assistant for selected Hubitat devices through the MCP Rule Server.

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
