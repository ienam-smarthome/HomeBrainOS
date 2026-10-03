# Hubitat MCP AI 0.16.99

## Immediate Internet block/unblock semantics

- Immediate `block` / `unblock` / `allow internet` requests now use the same authoritative Hubitat `Internet` room contract as scheduled Internet control.
- Semantic `blockInternet` is compiled to real Switch `off`; semantic `allowInternet` is compiled to real Switch `on`.
- The selected device is re-read by authoritative label and must advertise the real `off`/`on` command immediately before the write.
- Verification waits for the literal `switch` attribute to converge to `off`/`on`; it no longer depends on a synthetic `internetAccess` attribute.
- Natural room-local identity matching covers the live `unblock M6 ultra PC` -> `Block PC-NucBox-M6Ultra` case without changing the global device resolver.
- Bare `unblock <target>` is admitted only into this room-scoped deterministic path; a target outside the authoritative `Internet` room fails closed without a device command. Bare `restore <target>` remains excluded unless the user explicitly says internet/access because `restore` is overloaded with backup/settings operations.
- Ambiguous or missing Internet-room targets fail closed; ordinary similarly named devices outside the Internet room cannot win.
- Fresh structural identity cache is reused first, preserving the low-latency path introduced in 0.16.98.

## Regression coverage

- Immediate TV block sends `off`, not `blockInternet`.
- Immediate TV allow sends `on`, not `allowInternet`.
- Exact live phrase `unblock M6 ultra PC` resolves the Internet-room M6 control and sends verified `on`.
- Bare `unblock` of a non-Internet target sends no device command.
- Scheduled requests remain handed to RuleAuthoringService unchanged.
