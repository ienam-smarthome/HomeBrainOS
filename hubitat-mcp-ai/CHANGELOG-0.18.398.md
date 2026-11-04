# HomeBrainOS v0.18.398 — hub driver timed Internet pilot

- Added a narrowly-scoped hub-resident timer client for the user's Cudy
  Managed Device Block instances. Delayed Internet-block requests enter a
  bounded, device-driver-attested preflight before the pre-existing native
  Rule Machine scheduled-command fast path.
- Retained the existing immutable host confirmation lifecycle for all timer
  mutations. Explicit driver IDs, protected-system exclusions and sequential
  bounded MCP batches prevent an ambiguous or broad device command from
  silently modifying infrastructure.
- After approval, read both driver timer attributes and compare timedBlockAt
  with the requested relative deadline. Only matching read-back supports an
  armed-timer receipt; execution at the deadline and router enforcement remain
  unverified until live observations exist.
- Added offline regression tests for target resolution, protected devices,
  ambiguous names, partial/uncertain command acknowledgments, deadline
  mismatch, missing Groovy patch, command batching, cancellation and tool
  effect classification.
- The separate Cudy Managed Device Groovy patch in the user-provided design
  has NOT been compiled or installed by this release. The accompanying setup
  note identifies risks in the original 07:00 timer clear, manual allowance
  and hub reboot/misfire guarantees. Do not assume the driver is ready.
- No rules, virtual devices, Hubitat apps, installed drivers, OpenWrt router
  settings or physical device states were changed during development.

Release note status: offline code staged for GitHub CI; real on-hub
acceptance requires a separately audited driver update and live testing.
