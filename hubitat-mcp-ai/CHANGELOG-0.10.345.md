# Hubitat MCP AI 0.10.345

## Fixed

- `natural_datetime.format_natural_datetime()` silently fell back to the raw
  ISO string instead of natural-language text whenever it ran on Python
  3.10 or earlier and the input carried a colon-less UTC offset (Hubitat's
  own format, e.g. `...23:32:52.656+0100`) -- `datetime.fromisoformat()`
  only accepts that shape starting in Python 3.11, and the fallback
  `except ValueError` masked the failure instead of surfacing it. The
  add-on's `Dockerfile` installs Alpine's unpinned `python3` package, so
  whether this fired in production depended on whatever Python version
  Alpine resolved at build time. Fixed by normalising a trailing
  `[+-]HHMM` offset to `[+-]HH:MM` before parsing, so behavior no longer
  depends on interpreter version.
- Precise-location device attributes (GPS `latitude`/`longitude`, resolved
  street `address1`/`address2`, the rendered map `tile` HTML, and
  `journeysToday`/`journeysYesterday` travel logs -- as returned by Life360
  and similar presence-driver families from `hub_list_devices`) were sent
  unredacted into the `tool` role message appended to the provider
  conversation on every request that touched a presence-capable device.
  With `ollama_direct_cloud_enabled: true` (the setup docs' primary
  configuration), that meant a household member's exact coordinates, home
  address, and minute-by-minute movement history left the network to
  Ollama's cloud API just to answer ordinary presence questions --
  contradicting this project's "privacy-preserving local control"
  positioning. `EvidenceRecorder.redact()` only ever scrubbed credential-like
  *tool call arguments* (`password`, `token`, etc.); nothing redacted *tool
  results*. Fixed with a new `location_privacy.redact_precise_location()`
  pass wired into `ToolExecutor.result_payload()` -- the single choke point
  every provider-bound tool message passes through -- so only the sensitive
  location fields are withheld. `presence`, `battery`, `wifi`,
  `resolvedPlace`, and timestamps are left intact, so "is anyone home"
  style questions are unaffected.

## Context

- Both bugs were found via a live review against a real Hubitat hub:
  running the existing test suite reproduced the datetime fallback
  directly (`format_natural_datetime("2026-08-03T23:32:52.656+0100")`
  returned the input unchanged instead of "11:32 pm on Monday 3 August
  2026" on Python 3.10.12), and a live `hub_read_devices` call against a
  populated hub returned real Life360 attributes (GPS, address, HTML map
  tile, journey log) that traced straight into
  `mcp_agent_orchestrator.py`'s provider message list with no redaction
  step anywhere upstream.

## Scope, stated honestly

- `location_privacy.py` redacts by attribute *name*, not by driver type --
  it does not need a Life360-specific allowlist, but it also means any
  future driver that happens to reuse one of these exact attribute names
  for a non-sensitive purpose would also be redacted from provider-bound
  content. None currently do.
- This redacts what reaches the *provider*. It does not change what the
  deterministic local-answer path (`present_tool_result`, which never
  leaves the box) shows the user directly, since answering "where is X"
  from the user's own assistant using their own hub's data is the expected
  behavior; only the cloud/local-LLM-bound copy is scrubbed.

## Validation

- Adds `tests/test_location_privacy.py` (redaction correctness, presence
  data preserved, non-location devices untouched, scalar/list/None inputs)
  and a `tests/test_tool_executor.py` regression test asserting GPS values
  never appear in `ToolExecution.content`.
- `tests/test_natural_datetime.py::test_formats_iso_timestamp_as_natural_local_time`
  now passes on Python 3.10.12 (previously the one failing test in the
  suite on this interpreter).
- `python3 -m pytest -q` (550 passed).
- `python3 scripts/validate_addon.py` and `scripts/analyze_imports.py` both
  clean; `location_privacy.py` added to `docs/RUNTIME-MODULE-MAP.md` in
  this commit (zero orphan modules).