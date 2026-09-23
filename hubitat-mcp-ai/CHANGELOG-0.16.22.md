# Hubitat MCP AI 0.16.22

## Faster direct causal provenance

0.16.21 completed the MCP Rule Server 4.4.1 provenance integration and was
live-verified against the real Dehumidifier 2 history.

Observed 0.16.21 causal baselines:

```text
Why did Dehumidifier 2 turn on?
tool_calls: 4
causal_command_producer_reads: 2
mcp_concurrent_peak: 2
total: 1.1 s

Why did Dehumidifier 2 turn off?
tool_calls: 4
causal_command_producer_reads: 2
mcp_concurrent_peak: 2
total: 836 ms
```

Both already finalized deterministically with zero model rounds and zero native
log reads. 0.16.22 therefore focuses only on reducing the remaining remote-read
critical path.

## Requested command only

An explicit causal question already identifies the boundary that needs direct
producer proof:

- turn-on question -> `command-on`
- turn-off question -> `command-off`

The opposite command producer was useful extra narrative context, but it was
not required to prove the requested transition.

0.16.22 now reads only the requested command direction for explicit causal
prefetch.

General history callers that request command provenance without an explicit
causal transition keep the existing richer behavior and can still collect both
ON and OFF command rows for a closed interval.

## Parallel switch + command reads

The requested command-history read now starts at the same time as authoritative
switch history.

This intentionally uses the existing MCP client concurrency limit of two:

```text
switch history  ─────────────┐
                             ├─ run concurrently
requested command history ───┘
```

The global Hubitat/MCP concurrency setting is not increased.

Expected explicit-causal shape:

```text
tool_calls: 3
causal_command_producer_reads: 1
mcp_concurrent_peak: 2
model_rounds: 0
causal_native_log_reads: 0
```

The three counted tool calls are the two remote authoritative reads plus the
local HomeBrain device-history tool.

## Keep useful interval context

Removing the opposite command read does not remove the observed run duration.

The switch timeline already contains the interval boundaries, so deterministic
answers can still report context such as:

```text
The observed run ended when the device reported OFF at 8:27:23 AM,
after 1 hour 30 minutes.
```

or:

```text
This ended an observed run of 1 hour 30 minutes, which began when
the device reported ON at 6:57:23 AM.
```

The answer no longer names the opposite command producer unless that provenance
was actually fetched by a richer/general history request.

## Safety and fallback behavior

- The authoritative switch-history read remains mandatory.
- The requested command row must still precede its state boundary within the
  established correlation tolerance.
- If requested command provenance is absent, HomeBrain retains the existing
  native-log/model fallback behavior.
- If the switch-history read fails while a command prefetch is in flight, the
  command task is cancelled and awaited cleanly.
- Driver-filter fallback for switch history remains unchanged.
- No global MCP concurrency increase is introduced.

## Regression coverage

0.16.22 adds/updates tests for:

- ON causal requests performing one `command-on` producer read;
- OFF causal requests performing one `command-off` producer read;
- total explicit-causal tool count reduced from four to three;
- switch history and the requested command read actually overlapping;
- peak causal read concurrency remaining two;
- general provenance history without an explicit transition still reading both
  command directions;
- closed-interval duration retained when the opposite command producer is not
  fetched;
- MCP 4.4.1 structured provenance remaining compatible;
- zero provider/model rounds and zero native-log reads when direct provenance is
  sufficient.
