# Hubitat MCP AI 0.16.9

## Bounded concurrent MCP requests

0.16.8 live testing reduced clear semantic two-light controls to roughly two
seconds, making the remaining MCP serialization visible. Independent attribute
reads and verified device writes were started concurrently by
`DeviceControlService`, but every MCP request still queued behind one global
client lock.

0.16.9 narrows that lock rather than removing safety controls globally.

### What remains serialized

The client still serializes:

- MCP session initialization;
- the initialized notification;
- tool-catalog refresh/mutation;
- cacheable aggregate live-device snapshots, which remain single-flight.

### What can now overlap

Ordinary MCP operations run through a bounded semaphore. The default is:

```yaml
mcp_max_concurrent_calls: 2
```

This allows two independent per-device reads or verified writes to be in flight
at once. A room control for two lights can therefore overlap both live level
reads and both `setLevel + waitFor` operations instead of forcing the second
operation to wait for the first to complete.

The limit is intentionally conservative and is clamped to 1-8.

Set:

```yaml
mcp_max_concurrent_calls: 1
```

to restore serialized ordinary MCP traffic without reverting the release.

## Cache and session safety

Structural identity TTLs and snapshot generations are unchanged. Aggregate
device snapshots keep a dedicated single-flight lock, and the existing manifest
and live-context coalescing remain intact.

JSON-RPC request IDs are still generated synchronously before each request.
Session initialization remains complete before ordinary calls enter the bounded
request gate.

## Observability

Adds:

- `mcp_concurrent_peak` — maximum concurrent ordinary MCP requests observed
  during the HomeBrain request;
- `mcp_queue_wait` — cumulative time waiting for a bounded request slot;
- `mcp_session_lock_wait` — time waiting for serialized session/tool-catalog
  mutation.

The legacy `mcp_lock_wait` metric remains accepted for compatibility with
older traces, but ordinary 0.16.9 traffic should primarily report the new queue
and concurrency metrics.

## Regression coverage

Tests prove that:

- two independent verified writes can overlap when the limit is 2;
- the limit is respected;
- setting the limit to 1 restores serialized calls;
- concurrent aggregate snapshot callers still result in one upstream POST;
- request metrics retain the maximum concurrency peak rather than summing it.
