# Scheduler ownership: native link preservation

## Source-level finding (2026-10-09)

The upstream `kingpanther13/Hubitat-local-MCP-server` `libraries/mcp-diagnostics-lib.groovy` reads `/logs/json` in `_logsJsonFetchAndPublish` and reduces `data.jobs` to `id, name, recurring, method, nextRun`. This drops the native `link` and `nextRunDt` fields where available. `toolGetHubJobs` returns those projected rows. Thus the HomeBrain v0.16.152 observation of exactly five scheduler fields describes this projection, **not proof that Hubitat lacks owner metadata**.

A Hubitat community example shows `link: "/installedapp/configure/2382"` on a scheduled app job: https://community.hubitat.com/t/find-upcoming-cron-jobs-for-a-specific-method-in-app/159549/9 .

## Upstream proposed read-only change

In the `jobs: _logsJsonTable(data, "jobs").collect { job -> ... }` projection, retain only allowlisted internal link shapes; never return arbitrary URLs or accept external domains. Example:

```groovy
jobs: _logsJsonTable(data, "jobs").collect { job ->
    def row = [
        id: job.id, name: job.name, recurring: job.recurring,
        method: job.methodName, nextRun: job.nextRun
    ]
    def link = job.link instanceof String ? job.link.trim() : ""
    def appMatch = link =~ /^\/installedapp\/configure\/([1-9][0-9]{0,8})(?:\/[A-Za-z0-9_-]+)?$/
    if (appMatch.matches()) {
        row.ownerLink = "/installedapp/configure/${appMatch.group(1)}"
        row.ownerLinkType = "installed-app"
        row.ownerLinkSource = "/logs/json"
    }
    if (job.nextRunDt instanceof String) row.nextRunDt = job.nextRunDt
    return row
},
```

**This is illustrative code, not a merged or tested patch.** Consider device-link patterns only after observing and validating their actual native format; do not guess a device path. Preserve backward compatibility with the existing fields and pagination. Add tests for valid app link, no link, malformed link, external URL, encoded traversal, misleading id, and large snapshots.

## HomeBrain consumer design

- Recognize the new `ownerLink` only with exact expected shape and `ownerLinkSource=/logs/json`; do not treat arbitrary strings as trusted.
- An app link is direct **native scheduler owner-reference evidence**; verify the linked installed-app ID against the app inventory or a bounded `statusJson` read before labeling it confirmed.
- Cross-check matching job handler and/or per-app scheduled jobs when available; report mismatches and unresolved cases explicitly.
- Keep scheduler key patterns as candidates only; do not infer owners from key or from name alone.
- Do not claim scheduled entries executed, consumed CPU, are orphaned, or can be removed safely from ownership alone.
- Keep all checks read-only and bounded, and avoid diagnostics that themselves generate misleading error logs.

## Access limitation

The GitHub connector can read `kingpanther13/Hubitat-local-MCP-server`, but a branch-creation attempt returned HTTP 403 (Resource not accessible by integration). An upstream change therefore needs write permission or an authorized fork/PR workflow. No upstream repository or Hubitat hub has been changed.
