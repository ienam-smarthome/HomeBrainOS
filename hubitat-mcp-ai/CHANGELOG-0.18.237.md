# v0.18.237 — bound failing MCP reads and distinguish inaccessible history

## Source of the change

A real V2 test of the most recent complete heating ON/OFF cycle took
**110.789 seconds**. Five MCP READs on multiple gateways timed out at
about **20 seconds each**. One unrelated application list succeeded,
but no target-device event history was retrieved. The add-on then
published an insufficient-cycle answer that sounded as though it had
examined target events. The user-facing cause of this failed investigation
was **source access**, not established absence of historical events.

## Reliability changes

- Add a per-investigation READ health circuit breaker. **Two consecutive
  timed-out MCP reads**, even across separate gateways or operations,
  terminate the tool-planning loop. A successful READ resets the consecutive
  timeout counter; an ordinary gateway error does not falsely certify
  recovery. This is a local experiment-state breaker, not a claim about
  the availability of the hub or the wider network.
- Cap model-selected broad inventory/discovery reads at **5 seconds**;
  cap scoped and other reads at **10 seconds**, respecting tighter caller
  budgets and the remaining investigation deadline. The model still
  chooses the operation and arguments; the host only limits execution cost.
- Distinguish three source-observation states for an explicitly requested
  complete operating cycle: a verified pair of state transitions;
  a successful source history with no verified pair; or **no target event
  history read at all**. Only the middle case may be described as a
  negative observation in the *returned sample*. A timed-out device read
  is never negative historical evidence.
- If the target history was never retrieved, give a direct natural-language
  tool-access failure, do not publish irrelevant app metadata as a cycle
  diagnosis, and preserve the detailed failing operations and local circuit
  state in diagnostics.
- Keep existing evidence-citation requirements and all read-only,
  source-verified identity and scope guards. The circuit never issues
  a fallback write or automatically changes automation settings.

## Remaining external work

This release **does not establish why the hub stopped answering MCP
requests**. That requires live investigation of the Hubitat MCP server,
network/session lock, HA add-on process and other source-side telemetry.
A unit test that simulates a timeout verifies safe behaviour but cannot
prove the live connection is healthy. Avoid repeating lengthy causal
investigations when the source is timing out.
