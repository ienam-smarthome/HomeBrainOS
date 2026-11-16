# HomeBrainOS V2 alpha.134 — evidence-tiered source-only partial answers

**Status:** PR candidate; exact-head CI and installed source-real acceptance pending.

## Verified problem

An installed V2 alpha.133 first answer retrieved an original successful
\`hub_list_device_events\` history for the named light with a source-attributed
\`command-off\` and a later bridge-reported OFF state. The model overstated
physical causation; the causal publication floor correctly withheld that
definite claim, **but the source-only fallback discarded all native
\`command-*\` rows**. The published answer therefore lost a genuinely
reported command issuer even though it had the receipt.

This is a generic **partial-answer evidence-loss** defect, NOT proof that
the original model selected sufficient sources to establish the upstream
button/automation trigger. The first-answer review scored the original
alpha.133 answer 3/8 for the four qualitative dimensions. This alpha.134
change is not a scored accuracy improvement until installed live review.

## Implementation

- Preserve original identity-bound native \`hub_list_device_events\`
  command rows. Support both the explicitly identified device envelope and
  the real upstream legacy shape where the requested device ID is carried
  only in the executed successful original tool arguments.
- Accept only native \`command-[A-Za-z][A-Za-z0-9]*\` event names with
  timezone-aware original event timestamps and optional \`type=command\`.
  A recorded \`producedBy.appId\`, when an ordinary numeric ID, identifies
  **who issued the recorded command**, not their internal trigger.
  A \`triggered[]\` observer, a bridge-reported state, current inventory
  metadata or an arbitrary app-filtered event query never substitutes for
  command provenance.
- Keep at most one most-recent example **per distinct command name** per
  device, bounded to six commands/three history targets. This prevents
  multiple later dimming or setpoint commands from crowding out an earlier
  recorded ON/OFF command. Do not assume any listed device is the
  question's focal output when multiple devices are read.
- Preserve device-reported state observations separately and label a
  source-reported device producer as the **reporter**, not the issuer.
  State reports do not prove physical outcomes; event proximity does not
  establish causality or exclusivity. Internal controller decisions and
  unread event-time execution logs remain unverified.
- Retain source-only partial status and existing publication floor. If a
  native device page hits its requested row limit, explicitly disclose
  that fact and unknown historical coverage. Valid command-only native
  history is evidence even when no state row exists.
- Preserve no-live-write and no-extra-call property. V1, heating scheduler,
  native write permissions, approval cards, model route, provider prompts,
  autonomous source selection, and the external unmerged regex patch are
  unchanged.

## Expected effect, risks and measurement

**Hypothesis:** When a model's unsupported causal conclusion is replaced
with a source-only partial answer, the user should still see the actual
source-verified command issuer, if any, and separate device state reports.
This should increase informational usefulness without asserting an
independently verified physical effect or upstream controller cause.

**Regression risks:** More bounded metadata in partial answers; an unverified
source field could be mistaken for authoritative physical causation; wrong
device attribution if identity binding is too permissive; duplicated or
conflicting producer rows; leaking untrusted free-text fields. Mitigations:
original exact requested device identity, bounded command names/IDs,
sanitised producer labels, no listener promotion, source-only status,
explicit physical/decision caveats, fictional cross-domain tests.

**Testing:** Fictional unit and agent-level tests cover overlapping new
brightness commands versus older recorded OFF, state bridge as reporter,
command-only history, thermostat setpoint commands, listener-only
provenance, conflicting issuers, malformed dates, wrong IDs, non-device
source envelopes, failed reads, row limit and no additional MCP calls or
writes. Run the whole Python suite and V2 pilot/UI/release workflows.

**Installed acceptance:** Update V2 Preview to alpha.134, start a fresh
read-only investigation, and send the FIRST answer plus PRIVATE Technical
JSON. Verify that a causal-publication partial still lists original
command issuer and bounded report chronology when source rows actually
contain them. Review whether the model's normal answer is correct separately.
A safer, more useful fallback **does not pass the original autonomous
root-cause explanation objective**. No CI result is a live model score.

**Rollback:** Revert the V2-only alpha.134 PR or restore alpha.133.
No device state migration or new settings are needed.
