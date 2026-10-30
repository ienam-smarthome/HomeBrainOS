# v0.18.247 — investigate a recent cycle just outside an empty query window

## 30 October 2026 live discrepancy

At 14:19:25 GMT, Claude and original HomeBrain both found no ON/OFF events
during the strictly requested 12:19:25–14:19:25 window. Claude also checked
the last significant Bathroom/ Shower cycle from 12:10–12:18:52, ending
approximately 33–60 seconds before the boundary, and compared occupancy/
motion edges. HomeBrain queried each light's most recent two-hour native
Hubitat history (0 results), then broad hub logs, and concluded no activity
without consulting the already available Historical Journal.

The original group journal recovery only ran when source device histories
contained *some* command or level records. When all three native histories
were empty, `collect_unified_evidence` returned no incident facts and the
journal was never queried. Empty queried histories do NOT prove inactivity.

## Original-agent correction

- Add read-only `recent_edge_context.py`. For a bounded relative-period
  history question with 2–5 independently verified device identities,
  require independently performed successful device-specific native history
  reads for **every** target. If those reads all return zero in-window switch
  events, use the existing local Historical Journal for a source-attested
  check of the requested period and up to **15 minutes immediately before**.
- Never expand a fixed historic date/window implicitly. Never scan unknown
  IDs, unbounded app logs, or the user's whole hub. Results are capped to
  100 journal events per named light, and the entire 15-minute extension
  is labelled as **outside** the exact requested period.
- If the journal finds in-window switch observations, explicitly correct an
  unsupported earlier 'no activity' conclusion. If only preceding source
  records are found, show a concise earlier cycle while keeping the
  strict-window finding. Collector-received duplicates are not counted as
  independent original switch changes.
- Journal gaps, unverified source time, missing sensor/automation decision
  records and lack of upstream command attribution remain explicit.
  **No initiator is inferred** from a Hue Bridge reporter, a later
  brightness adjustment or mere temporal proximity. The original agent's
  verified evidence and read-only permission boundaries remain intact.
- All-app 48-hour log retention from v0.18.246 remains unchanged.
  No Investigation V2 test UI/agent is restored.

## Regression

Replay all three verified named lights with exact empty Hubitat histories,
journal source-timed ON/OFF changes in the adjacent 15 minutes, a
collector-received duplicate, an independently observed switch inside the
strict period, missing identity/history checks, and the actual original
Main Ask final response boundary. Run full Python, repository validation,
Hubitat MCP AI tests, release assurance and add-on container smoke before
merging. Live Home Assistant deployment and the original ON initiator still
require separate verification.
