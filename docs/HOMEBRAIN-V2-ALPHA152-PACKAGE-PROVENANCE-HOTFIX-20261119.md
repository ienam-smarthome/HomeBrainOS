# Alpha.152 acceptance hotfix — installed package identity (19 Nov 2026)

## Source-real blocker

An installed alpha.152 Acceptance Study can display **"Add-on package unverified
(unverified)"** and refuse to start any first answer, with all ten cases still
`ready`. The user sealed an alpha152 manifest; it must not be deleted or
re-sealed. This is a packaging evidence bug, not a device or MCP permission
failure.

## Root cause

`acceptance_routes._package_identity` used a malformed raw regular
expression with double-escaped whitespace. It could not parse the
`version: "2.0.0-alpha.152"` field in the bundled `/app/addon-config.yaml`.
The container's `HOMEBRAIN_PACKAGE_VERSION` is optional in some Supervisor
build paths; when absent, both proof sources were effectively missing.

The previous CI route integration mocked `_package_identity` and therefore
failed to reproduce the real parse.

## Narrow repair

- Parse the **top-level bundled manifest version** directly, supporting quoted
  and unquoted values with a bounded version character set. It is never read
  from user-provided labels, the sealed study manifest or the browser.
- If a nonempty `HOMEBRAIN_PACKAGE_VERSION` exists, it must still match
  the bundled manifest. A conflict is a hard error.
- If Supervisor omits the build arg, the bundled manifest may be used as a
  source-reported version **only if** the running server version also equals
  the frozen alpha152 pack version. The report explicitly labels this weaker
  provenance `bundled_manifest_no_build_arg`.
- If no bundled config, unreadable/invalid config, an explicit build mismatch,
  or any expected-version mismatch occurs, capture is denied.
- Extend the offline verifier to accept the same new labelled provenance only
  for alpha152. No old study or export is changed.
- Add direct package-parser fixture tests, one in-app capture and offline-report
  test with no build arg, and fail-closed mismatched/missing cases.

No model prompts, response content, native MCP queries, write permissions,
approval workflow or first-attempt semantics change.

## Deployment without discarding the sealed private study

The alpha152 version is **intentionally unchanged**: the frozen user's
`alpha152-prospective-v1` manifest expects exactly
`2.0.0-alpha.152`, and no first attempts were started. The corrected image
must be rebuilt from the latest repository commit on the installed add-on
using **Home Assistant > Settings > Add-ons > Hubitat MCP AI v2 > ⋮ > Rebuild**,
after refreshing the custom add-on repository. A normal Restart of the old
image does not apply new Python code. Do not uninstall the add-on, reset its
persistent `/data`, delete the sealed study or alter its labels.

After rebuild, the Acceptance Study should show:
`Add-on package 2.0.0-alpha.152 (bundled_manifest_no_build_arg)`
(or `build_arg_and_bundled_manifest_match` if the Supervisor build value
was supplied). Then capture each of the 10 `ready` cases once using the
dedicated MCP client with source-reported Read ON / Write OFF.

This is an **acceptance workflow correction**, not a quality promotion:
the captured alpha152 first answers and independent factual scoring are
still pending.
