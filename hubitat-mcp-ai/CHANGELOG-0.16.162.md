# 0.16.162

- Enhance the read-only deterministic `check <room> status and states` route to verify explicitly linked parent devices using Hubitat MCP's authoritative `parentDeviceId` metadata.
- For missing room-list parents, perform a bounded targeted `hub_get_device` read (up to four unique parents) without guessing parent relationships from device labels or IDs.
- If the parent explicitly reports offline or a connection fault, show its observed diagnostic status in Device Health and treat dependent children's motion, presence, illuminance and other retained data as unverified.
- If the parent is not authorized for MCP access or cannot be read, **do not claim it is offline**. Display a "Connection unverified" warning, indicate that the MCP Rule Server device selection may need updating, and keep dependent readings out of confirmed current room observations.
- When the parent explicitly reports healthy/connected and no contradictory connection status, preserve the children's current reported states; when parent status is absent, fail closed as unverified.
- Avoid duplicate parent probes and unnecessary extra requests when no parent link is present; preserve unrelated device states and offline sensor handling from 0.16.161.
- Regression tests cover Aqara FP2 child-to-parent 7334 linkage, offline parent, inaccessible parent, recovered/connected parent, unknown health and the one-extra-targeted-read route.

Read-only. No device-control changes. Parent data cannot bypass Hubitat MCP device authorization; a parent that isn't selected for MCP access remains unverified rather than falsely classified.
