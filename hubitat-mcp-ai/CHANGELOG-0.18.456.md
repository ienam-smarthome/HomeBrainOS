# HomeBrainOS v0.18.456 — Past-log request and focal evidence scope

## Changed

- Recognise native default past mode when omitted. Count every successful read independently of whether it has a valid bounded window; exclude failed, mutating and explicit nonpast calls.
- Share normalised scope across claim shadow and failed-repair factual floor. Keep requested window overlap separate from returned focal rows or historical completeness. Naive, invalid, reversed or source-rejected filters cannot attest focal coverage.
- Add privacy-safe `log_request_coverage` with past reads, bounded requests, unbounded/invalid requests, app-scoped reads and separate general/app focal overlap. Existing `app_log_requests` remains the legacy total past-read count.
- Check source-attested focal log absence at synthesis and final read-only publication. Preserve truthful returned-query observations and positive facts. Bound unqualified no-hub-command assertions to returned command records.
- Keep issuing-app decision reads anchored to matching source-attested focal OFF commands; do not use unrelated historical method commands.
- Clarify source-role instructions without extra model or MCP calls. No new module, device change, provider routing, billing or confirmation change.

## Evidence and validation

The supplied installed v0.18.455 JSON proves the shadow integration is active, not that the model's prose is fully validated. The new adapter locally replays its four implicit past-log requests as 4 total / 1 bounded / 3 unbounded or invalid / 0 focal / 0 app-specific focal. No direct sensor window, relevant app configuration, full historical retention or initiating OFF controller is established. Private messages/identifiers are not copied into new fixtures.

Local Python compilation and original-packet adapter replay passed. Merged [PR #1518](https://github.com/ienam-smarthome/HomeBrainOS/pull/1518) after all four required workflows passed on exact head `555a77eef1545dbfb6650d20c3e3babd04f72c76`: Release assurance (**6,781 Python tests**, two nonblocking warnings, container smoke and metadata), Hubitat MCP AI tests, Validate HomeBrain OS and Answer Quality scorecard integrity. Squash merge: `2c44aa359d1e5a4c03c13c28ce4390cee7f412ae`. New fictional tests cover defaults, one-sided/offset/invalid windows, source rejection, failed/write/nonpast calls, scoped sample language, synthesis and final API, command selection and confirmation isolation. Installed v0.18.456 first-answer quality remains unverified; synthetic tests are not a production benchmark.
