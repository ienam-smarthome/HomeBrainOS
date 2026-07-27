# Hubitat MCP AI changelog

## 0.10.183

### Migrate final deterministic read routes into the shared registry

- Registers device-health, attention and whole-home priority reads in the existing
  read/execution registry.
- Registers grouped Octopus whole-house energy reads in the same registry.
- Removes the two remaining direct deterministic read wrappers from
  `entrypoint_core.py` while retaining compatibility installers for standalone
  consumers and historical tests.
- Keeps query-classification metadata hooks separate from answer routing.
- Reduces the maintained live request stack by two wrappers without changing
  deterministic route behavior.

## 0.10.182

### Complete the final request-layer registry audit

- Adds an executable audit for the maintained four-registry request composition.
- Verifies migrated legacy answer-guard and terminal-route installers are not
  reinstalled by `entrypoint.py` or `entrypoint_core.py`.
- Verifies request composition is finalised before direct runtime HTTP route setup.
- Marks request-routing Thread 1 step 3 complete when the audit and existing CI
  suite are green.
- Leaves the optional planner redesign deferred and identifies Device Health
  Monitor state bloat as the next independent workstream.

## 0.10.181

### Consolidate read routes with execution guard

- Registers named Rule Machine status reads, climate extrema reads and the
  execution-contract answer guard in one ordered `AnswerGuardRegistry`.
- Preserves named-rule-first and climate-second terminal routing followed by
  execution-contract annotation.
- Removes one redundant request wrapper without changing any route or guard.
- Keeps runtime HTTP route rebinding outside request composition.

## 0.10.180

### Consolidate summary and thermostat guards

- Registers the thermostat live-state terminal route, home-summary consistency
  guard and thermostat-summary guard in one ordered `AnswerGuardRegistry`.
- Preserves thermostat-first routing followed by home-summary consistency and
  thermostat-summary post-processing.
- Removes one redundant request wrapper without changing any route or guard.
- Keeps the consolidated registry between semantic-home handling and the
  read-only terminal-route registry.

## 0.10.179
