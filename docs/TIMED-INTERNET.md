# Hub-resident timed Internet blocks — preliminary integration

This feature is intended for Cudy Managed Device driver instances with labels
such as Block Media-Google-TV-Streamer (device ID 6923). It does not create
Rule Machine rules, virtual devices, or per-request Hubitat apps.

## Before enabling writes

1. Back up the installed Cudy Managed Device Groovy source (driver code ID
   3552, according to the user's attached brief). The source has **not** been
   independently fetched or compiled on a live hub in this release.
2. Have the owner apply and test an audited driver patch adding
   blockInMinutes, allowForMinutes, cancelTimedBlock, timedBlockMins and
   timedBlockAt. The HomeBrain add-on cannot install the driver patch.
3. Save Preferences on one test device, verify both timer attributes report
   valid values, then test a one-minute block manually from its device page.
   Restore Internet access with allowInternet/on afterwards.
4. Enable the normal Hubitat MCP device-write permission, read-only guide-key
   flow and recent-backup preflight. Writes require approval in HomeBrain.

## Important corrections to the supplied Claude prototype

- Do **not** enable automatic morning cancellation at 07:00 by default: it
  silently defeats legitimate pending blocks due after 07:00.
- A manual allowInternet command needs a clear policy for pending timers.
  The prototype only cancels them on blockInternet, contradicting its own
  claim that later manual allowance preempts a scheduled re-block.
- Hubitat runIn scheduling may persist through reboot, but if the hub is
  unavailable when a deadline passes, a scheduled callback may be missed.
  Test the hub's misfire behaviour, and include a state-based overdue
  reconciliation route in the driver before claiming reboot-time reliability.
- Saving driver preferences calls updated(), which may unschedule all jobs;
  restore a future pending deadline after rescheduling routine driver jobs.
- Timer-minute attributes may be snapshots rather than a continuously ticking
  countdown when sessionTick is inactive. timedBlockAt is authoritative for
  the driver-reported target instant; do not infer a live decrement from an
  unchanged timedBlockMins.
- A command receipt and matching timer attributes are evidence the driver
  *reports an armed timer*. Neither proves that the callback will fire later
  nor that router enforcement has actually completed.
- Do not install the uncompiled reference patch without comparing it with
  the current driver methods and testing one harmless device.

## HomeBrain commands

After the driver patch is installed and verified:

- "Block TV after 30 mins" enters a deterministic preflight that resolves the
  real Cudy Managed Device, verifies timer attributes and asks for confirmation.
- "Block Google TV in 2 minutes" also uses the hub timer, not Rule Machine.
- "Cancel the Google TV timer" and "What Internet timers are pending?" use the
  homebrain_timed_internet tool when selected by the model.
- "Block phone in 10 minutes" must resolve uniquely; ambiguous names do not
  trigger commands.

Every modifying homebrain_timed_internet invocation is classified as
sensitive_write and requires a valid host confirmation, including a one-device
request. The model cannot bypass it with a confirmed=true argument. Protected
network/hub devices are always excluded from bulk selection and refused for
direct timed writes, even with an exact name. Commands use device IDs and batch
at most 20 entries, sequentially.

## Acceptance — not yet established on the live hub

- Run the offline release gate and inspect CI.
- Confirm device 6923 has the **Cudy Managed Device** driver, not Cudy Category
  Device, and advertises the new commands and both attributes.
- Confirm one-minute manual block, observed switch/internetAccess transition,
  and successful Allow Internet restoration.
- Test the HomeBrain confirmation; check its receipt contains the expected
  device ID and driver-reported local deadline.
- Restart HomeBrain mid-countdown; verify Hubitat still fires the block.
- Test Hubitat reboot before deadline and a reboot spanning the deadline,
  explicitly documenting any missed job.
- Check cancelling a timer removes the pending job and both attributes return
  to zero/none. Save Preferences while armed and verify re-arming.
- Inspect the previous Rule Machine one-shot and cleanup scheduler separately.
  This new driver feature does not need or modify either.

**No live Hubitat/Router changes were made as part of the repository work.**

## v0.18.399 preflight performance

The initial v0.18.398 live request spent 37.95 s in MCP HTTP before it
offered confirmation. This release removes the expensive detailed all-device
manifest from the driver preflight and requests only a filtered summary with
id, label, driver and bounded cursor pages. It does not cache a write identity.
Before confirmation it still independently reads the selected driver's
timedBlockMins and timedBlockAt attributes. The approval replay re-reads
complete device identity before issuing the command.

Technical JSON now includes a timed_internet_preflight timing (ms) and
summary-preflight counters. Record a new live command after installation to
measure whether the preflight actually improved. The previous 38.16 s and
1.8 s observations are the v0.18.398 baseline, not v0.18.399 results.
