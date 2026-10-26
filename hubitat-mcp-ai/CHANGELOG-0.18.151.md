# HomeBrainOS v0.18.151 — Source-backed V2 incident evidence summary

The .150 Bedroom 3 Mesh test completed in ~45.9 seconds, retrieved 19
timestamped observations and one Rodret button ON command, and retained an
offline device snapshot. The short report, however, showed only the command,
hid all MQTT transitions and repeated health status changes, and labelled
UTC timestamps as "Local time". AI intent planning still timed out after
25 seconds, leaving the result in host-only fallback mode.

This update adjusts **generic evidence presentation** only:

- The short timeline retains commands, switch events, MQTT connectivity
  transitions and representative health status reports, within a bounded
  number of rows. It no longer allows repeated health flapping to hide the
  relevant transport sequence, or a lone command to obscure other states.
- Detect repeated alternation of `deviceHealth` between stale/unknown
  solely from canonical timestamped observations. This is a description
  of *Hubitat statuses*, not proof the physical device sent new data.
- An independently projected `lastSeen` in strict Hubitat BST/GMT format
  is compared with the *earliest actual returned source event*. When it
  predates the retrieved history, the report explicitly warns of a
  coverage gap without claiming source retention, event absence, physical
  failure time or root cause.
- Correct the report's table heading: undated V2 investigations display
  event timestamps in UTC, not falsely labelled hub-local time. Original
  source timestamps remain available in Investigation details.
- Synthetic regressions reproduce the complete salient .150 evidence
  pattern (MQTT disconnect/reconnect pairs, Rodret ON command, deviceHealth
  flips, lastSeen before earliest page) and invalid lastSeen rejection.

This does not resolve the underlying ~19-second complete inventory read
or the recurring 25-second semantic planning timeout. It does not add
device-specific rules, infer a cause, change a live device, or alter
production V1.
