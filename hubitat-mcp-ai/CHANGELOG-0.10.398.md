# 0.10.398

## Why this release

Third of four grouped releases closing Tier 2 findings from the
proactive full-codebase review conducted earlier this session (release 1
of 4, 0.10.396, shipped device-classification/tool-success consistency;
release 2 of 4, 0.10.397, shipped write-safety gating for the two direct
`hub_manage_*` tools). This release covers two robustness-hardening
findings: an unbounded pagination loop and a byte/character conflation
in the token-budget estimator.

## Fixed

**Unbounded pagination loop when fetching the device manifest through
the `hub_read_devices` gateway.** `mcp_client.py`'s `get_cached_devices()`
paged through `hasMore`/`nextOffset` with no iteration cap and no check
that `nextOffset` actually advanced between pages. A misbehaving or
malformed upstream response that kept reporting `hasMore: true` -- with a
repeating, regressing, or otherwise non-advancing `nextOffset` -- would
have looped forever, hanging the request. The loop now stops as soon as
the reported `nextOffset` fails to advance past the current offset, and
is additionally bounded by a hard `_MAX_DEVICE_PAGES` cap (200 pages) as
a backstop against a well-formed-but-unbounded upstream.

**Token-budget estimator silently conflated UTF-8 byte count with Python
character count.** `provider_token_estimator.py`'s `bytes_per_token`
profiles are calibrated against UTF-8 byte length, but
`chars_for_token_budget()` returned that raw byte budget directly as a
*character* ceiling -- callers slice Python `str` content by that count
elsewhere. That 1:1 mapping only holds for pure ASCII text; non-ASCII
text commonly runs 2-4 bytes/char (Latin-extended/Cyrillic/Greek ~2,
CJK ~3, emoji up to 4), so non-ASCII-heavy content truncated to the
returned character count could still exceed the intended UTF-8 byte --
and therefore real token -- budget. `chars_for_token_budget()` now
divides the byte budget by a documented `_MIN_BYTES_PER_CHAR` floor
before returning it as a character count, so the estimate stays
conservative for mixed-script text. This was already a soft gap in
practice -- callers `min()` the estimate against a hard, script-
independent character cap -- so this tightens an existing safety margin
rather than closing an exploitable gap.

## Validation

- `python -m pytest -q` -- 730 passed (5 new: a well-behaved paginated
  gateway still fetches every page and stops at `hasMore: false`; a
  gateway that repeats a non-advancing `nextOffset` stops after one page
  instead of looping forever; a gateway with a genuinely advancing offset
  but permanently `hasMore: true` is still bounded by the hard page cap;
  the character ceiling returned by `chars_for_token_budget()` is now
  strictly smaller than the raw byte budget and matches the documented
  `_MIN_BYTES_PER_CHAR` formula; the ceiling still scales monotonically
  with the token budget).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.398
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- This release closes findings #12 and #15 from the full-codebase review
  conducted this session (Tier 2). Apostrophe-free hub-health/firmware
  phrasing is tracked separately as the remaining grouped release.
