# Evidence class and diagnostic checklist

Evidence types: command invocation; observed device state; native app log; app configuration; scoped sensor/button event; physical bridge report; MQTT broker acknowledgement; requested-time topology; historical coverage.

Questions to ask:
- Did the relevant device receive a command, from which app, at what exact time?
- Did a conflicting state boundary occur between the command and the reported change?
- What is the typical response delay for comparable commands, when historical pairs exist?
- Does the controlling app expose a nested page or MQTT command topic? (Never expose its credentials.)
- Are a motion sensor's triggers or exclusions documented, or was it merely physically nearby?
- Is a rule active now versus known to have run at the event time?
- Are tool results truncated, stale, outside the requested window or a read with zero returned rows?
- What one next read would change the leading hypothesis?

Do not claim an external Hue/Matter controller initiated an event solely because producedBy on the *state report* names the bridge. Preserve command, report, and listener as independent directed edges.
