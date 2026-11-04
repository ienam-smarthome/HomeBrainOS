# Hubitat MCP AI v0.18.389 — virtual-device creation contract

## Why

The installed 0.18.388 real user trace attempted to create a disposable Hubitat
Virtual Switch by calling `hub_manage_devices → hub_create_device` with
`deviceTypeId="Virtual Switch"`. The MCP Rule Server 5.1.5 reported
"Could not resolve one supported native driver type" and explicitly
"No device create request sent." Confirmation succeeded, but the chosen
operation/parameter contract was wrong. This is **not** a Hubitat device
creation limitation or evidence that any switch was created.

## General change

- For a user-authorised *virtual-device creation* objective, expose the live
  `hub_manage_virtual_device` direct MCP tool schema already advertised by
  the server, even when fuzzy discovery ranks the generic device gateway first.
  This does not invent or enable any absent capability.
- Tell the model the actual type distinction: direct `deviceType` uses a
  virtual type label, whereas generic `hub_create_device.deviceTypeId`
  needs a supported native driver ID. Keep model-led tool argument selection.
- Reject virtual type labels supplied as generic native driver IDs **before**
  queuing confirmation, and revalidate them on confirmation resume.
- Keep the established user-write intent, write master gate, sensitive
  confirmation, guide/backup and resulting-state verification boundaries.
  No automatic retries, virtual switches, Rule Machine rules, router writes
  or network blocks are created by the upgrade.

## Before / after and measurement

- **Real before, one user receipt:** a confirmed generic create returned
  `success=false` / native driver type unresolved in **304 ms** on the
  confirmation execution attempt; no create request sent. One scenario, not
  a general benchmark.
- **After, offline:** fake-server regression tests exercise a misleading
  fuzzy gateway, direct-schema exposure, confirm-before-write, driver-ID
  rejection for multiple virtual types, and absent-tool non-invention.
- **After, installed answer and execution:** NOT MEASURED. The permanent
  Answer Quality scorecard remains **NOT MEASURED** (no authenticated,
  source-reviewed frozen first attempts from this change).
- No model/provider calls or real Hubitat/HA/OpenWrt access occur in tests.

## Risk, rollback and next validation

The extra direct schema is offered only for an independently authorised virtual
creation request. A faulty tool choice still fails closed; a disabled or
unadvertised direct tool remains unavailable. Revert this PR if unrelated
creation/confirmation requests regress. No BAT or Internet blocker can be
declared functional without independent live scheduling and enforcement reads.
The next eligible user interaction is a **read-only** question about the
available virtual-device tool schema or a nonmutating HomeBrain capabilities
inspection; do not treat this release as authorisation for a live write.
