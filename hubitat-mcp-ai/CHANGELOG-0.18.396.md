# HomeBrainOS v0.18.396 — align native Rule Machine summary with real MCP scalar shapes

## Observed baseline (actual installed output, not a synthetic pass)

A user-created **test rule** (`One-off block TV`, Rule Machine ID `4285`) was inspected read-only on installed v0.18.395. The source call succeeded in **730 ms**, with the correct 3 action IDs, but the answer discarded its saved 08:00 trigger, Switch OFF and ON and 15-minute wait. It incorrectly reported **69 of 71 settings as redacted/unsupported**, whereas the preceding v0.18.394 native field-by-field read reported only **6** redacted/unsupported. The submitted v0.18.395 receipt carried source read success, but not individual settings; the direct preceding v0.18.394 response supplied those fields. This release addresses a source-shape mismatch, not a Hubitat rule state change.

## Root cause and correction

The v0.18.395 natural-language renderer implemented a **second** setting validator. Unlike the existing native section reader, it rejected settings with optional `device_ids=null`; it also interpreted typed `bool` values only as Python booleans and typed numeric wait values only as Python numbers, although Hubitat form values may be strings. The source projection, not the rule, was being rejected.

- Share the existing `_simple_setting` privacy-safe projector with the native read path. Null or absent device metadata is omitted; valid capability switch device-ID lists remain source-checked. Redaction counts now have the same semantics as the detailed native reader.
- Decode only exact `"true"`/`"false"` values under the typed `bool` schema. Unknown, empty or untyped values remain unverified; never apply Python string truthiness.
- Decode only strictly bounded, integer-valued decimal strings under typed native `number` / `decimal` wait fields. Never interpret arbitrary prose like `"15 min"`.
- Maintain existing target-ID, time/date provenance, action order, unverified scheduled-job and physical device-effect qualifications. No extra MCP calls, model rounds or change to the native writer.

## Verification

Regression tests now include 71 source-shaped settings, null optional device IDs, form booleans as strings and typed numeric-string waits, as well as deliberately malformed values and privacy-sensitive fields. Confirm full CI results through PR; green unit tests are **not** a post-deploy live accuracy measurement.

**Post-install first-answer correctness and measured real-model performance: NOT MEASURED.** A fresh read-only repeat of the exact same named-rule request after installing 0.18.396 is required. No Hubitat/HA/router changes are made by this PR.

## Risk / rollback

Potential risk: sharing the canonical sanitizer changes a summary's acceptance of omitted device metadata; that metadata never establishes device identity. A summary can only name a device when a validated device-ID list is supplied. If a source read is incomplete, keep the fail-closed source result. Revert to 0.18.395 if source attribution, privacy or response format regresses.
