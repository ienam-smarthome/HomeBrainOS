# HomeBrainOS v0.18.391 — Q1 initial read-only model tool admission

## Hypothesis and outcome target

The installed v0.18.390 source-recovery test still showed one blocked
write proposal during a read-only question. The initial model-visible
tool declaration can include a discovered management gateway even when
no user mutation authority exists. A model call to that gateway is
already refused atomically, but wastes a provider round and contributes
no source evidence. Removing the *invitation* before the first model
round could reduce blocked proposals and improve source selection across
status, device, rule and network-read questions.

**Expected direction:** fewer initial blocked-write model batches,
no increase in model rounds or unneeded tool expansion, and at least
the same useful source-read coverage. Actual answer-quality gains,
first-attempt success, source-grounded factual accuracy, latency
median/p95, and cloud cost remain **NOT MEASURED**.

## Change

- Prune currently declared schemas to installed, effect-classified
  read-only tools before the **first** provider function-calling round
  whenever the request lacks independent user mutation authority.
- Preserve later explicitly discovered mixed-purpose management gateways
  for their verified read sub-operations, because some source documents
  have no equivalent dedicated read gateway. Unauthorized mutations still
  fail atomically through the unchanged per-call effect classifier.
- Keep initial read choices and schema ordering; do not automatically
  expand the starting list to 32 source tools, add provider rounds or
  synthesize fixed prose.
- Keep the existing atomic rejection of undeclared/model-proposed writes,
  sensitive confirmation, write authorization, installed capability
  registry and independently authorised create/control requests.
- No Hubitat, Home Assistant, router, Internet-blocker, timed-rule or
  disposable-switch change is performed by this repository release.

## Verification

Synthetic offline tests verify the initial read-only function schemas,
normal read execution, atomic handling of a malicious undeclared write,
independent catalog pruning, permitted later source discovery, and
preservation of the installed direct virtual-device writer for
separately authorised calls. GitHub Actions
full suite, metadata checks and packaging smoke tests are required
to pass on the **exact PR head SHA** before merge.

The prior single v0.18.389 -> v0.18.390 live receipt pair was
25,925ms -> 15,168ms (one measured pair, not a population speed metric),
with 2 -> 1 blocked write batches and 2 -> 7 source/read receipts
(including discovery and local projection). That pair evaluates the
*previous* version; it is **not** an after-test for this release.
The original source-claim completeness and factual quality are not
established by receipt counts.

## Risk, limits and rollback

Filtering writer tool declarations could hide a legitimate tool if a
user's write intent was incorrectly classified as read-only. Existing
authorisation is intentionally authoritative and unaffected; this
change makes a mistaken classification fail safely rather than grant
writes. Tests cover authorised virtual-device tool availability;
perform no live writes in this milestone.

Rollback: revert the source/catalog changes and release bump if any
required check fails or cross-domain read coverage regresses. A
reproduction must use the same prompt, provider/model, installed SHA
and actual first-run technical JSON. No unverified factual score
or Claude parity claim is justified.

## Next Q1 evaluation

Request a **new ordinary multi-device read-only HomeBrain question**
(the exact test prompt and complete first natural answer plus
technical JSON), then manually review value/scope evidence. Do not
reuse a live Internet blocker request as a guaranteed same-packet
model comparison, and do not infer a physical network block or a
scheduled device rule from tool-discovery receipts.
