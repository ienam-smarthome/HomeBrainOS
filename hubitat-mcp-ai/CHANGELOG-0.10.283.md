# Hubitat MCP AI 0.10.283

- Add `RuleAuthoringService`, a deterministic compiler for common daily
  start/end Rule Machine schedules.
- Resolve targets through bounded label filters and the shared name resolver,
  including space/hyphen variants such as `tab s9` and `Tab-S9-FE`.
- Verify both device commands before proposing any write; unsupported or
  ambiguous targets fail closed without queuing an action.
- Compile time windows into two independently named, single-trigger,
  single-action `hub_set_rule` calls and validate each payload locally.
- Check existing Rule Machine names when the read gateway is available so
  retries do not silently create duplicate rules.
- Queue the compiled calls through the existing structured confirmation store
  and retain strict post-confirmation ID, partial-state, and health checks.
- Keep advanced schedules in the native MCP discovery path rather than
  guessing unsupported recurrence or action structures.
