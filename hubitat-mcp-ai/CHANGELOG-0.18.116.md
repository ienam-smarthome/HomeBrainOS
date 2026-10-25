# HomeBrainOS 0.18.116 — Verify occupancy causal claims

## Live reproduction
On v0.18.115, the read-only Livingroom Light 1 investigation returned a
specific claim that false-motion ghosting was the most likely cause and
App 4019's off timer executed correctly in every observed case.
Retained events actually prove two OFF commands produced by App 4019
(16:58:58.691 and 17:01:16.922 UTC), each followed by a Hue Bridge OFF
state report (246ms and 173ms later).
An ON interval lasted 28m12s. The sampled motion activity of the
Livingroom Soft Sensor (device 7766, **a cloned sensor**) showed
only SenseCap D1 Settings app 4129 in its triggered listeners,
not controlling App 4019. This device is not one of the user-shown
activation/keep-on sensors configured for App 4019. The actual configured
FP400 activation input, Linptech Kitchen and Matter LWR01 keep-on inputs
were **not** all historically reconciled before drawing the conclusion.
A sampled device event page cannot prove the room was empty or that
every historic timer execution succeeded.

## Fix
- New read-only post-synthesis occupancy causal proof guard, applied at
  the stable API response boundary. Unqualified false-motion or ghosting
  diagnoses are converted to an evidence-grounded answer, keeping the
  verified longest bounded ON interval and app-produced OFF commands
  with measured follow-up state transitions.
- When sensor history includes triggered app listener metadata, report
  *only* that the observed cloned/unlinked sensor events do not identify
  the controller as a subscriber; do not infer the full app setting
  from missing subscriptions or count mirror devices as independent
  motion evidence.
- The investigative skill now requires the configured activation/keep-on
  input device IDs, each corresponding history and actual timer/command
  decision before blaming a sensor. Avoid a room-wide arbitrary sensor
  discovery path as a substitute.
- The guard does NOT assert a different root cause, issue Hubitat writes,
  modify device subscriptions or change any room settings.
- Add synthetic regression for the actual v0.18.115 output, timed
  command/state pairings, cloned event-source independence, incomplete
  command evidence and preservation of calibrated honest answers.

## Limitation
No software-only guard can establish physical vacancy from motion
events. A verified false detection requires independent occupancy
evidence, or at minimum a clearly identified and observed controller
decision framed as the app's *reported* occupancy rather than factual
empty-room proof. Live agent follow-up still needs validation.
