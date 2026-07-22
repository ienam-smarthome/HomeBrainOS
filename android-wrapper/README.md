# Hubitat MCP AI Android wrapper

A small Android WebView application that opens the local Hubitat MCP AI dashboard as a normal Android app. It appears in Samsung Modes and Routines under **Open an app or do an app action**, avoiding the Samsung Internet “routine opened this website” banner.

## Dashboard address

The default address is:

```text
http://192.168.1.208:8788/
```

To change it, edit `DASHBOARD_URL` in `app/build.gradle.kts`. For a different HTTP host, also update `app/src/main/res/xml/network_security_config.xml`.

## Build from GitHub

1. Open the repository **Actions** tab.
2. Run **Build Android wrapper APK**, or wait for the workflow triggered by a change under `android-wrapper`.
3. Open the completed run and download the `hubitat-mcp-ai-wrapper-debug` artifact.
4. Extract and install `app-debug.apk` on the Samsung phone. Allow installation from the browser or file manager when Android asks.

## Samsung Modes and Routines

After installation:

1. Open the app once and confirm that the dashboard loads.
2. Edit the routine.
3. Remove the **Open website** action.
4. Add **Open an app or do an app action**.
5. Select **Hubitat MCP AI**.

The wrapper permits HTTP only for the configured local host, blocks navigation to other hosts, disables WebView file/content access, and rejects invalid HTTPS certificates.
