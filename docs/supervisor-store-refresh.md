# Refreshing Home Assistant add-on metadata

If the Hubitat MCP AI release notes show a newer version but Home Assistant still displays the same installed and latest version, the add-on update entity is using stale Supervisor store metadata.

Restarting Hubitat MCP AI does not refresh repository metadata. Reload the Supervisor instead:

```text
ha supervisor reload
```

Then use **Settings → Apps → App store → ⋮ → Check for updates** and refresh the browser page.

If the repository still shows incorrect metadata, open **Settings → System → Logs**, select **Supervisor**, and check for repository validation or clone errors before removing or reinstalling the add-on.
