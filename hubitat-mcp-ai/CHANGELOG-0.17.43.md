# HomeBrain 0.17.43 — Typed decision claims, durations and effect verification

## Motivation — verified live 0.17.42 trace

The Livingroom manual-OFF investigation finally returned a bounded app-4019
log excerpt (`app-log-1`) that the synthesis quoted as:

> motion turn-on blocked for 300 min

The user had requested a **three-minute** motion lockout. The recorded log
statement was at **23:49:27.542 BST**, 13 ms after the OFF state report at
**23:49:27.529 BST**. The answer called the lockout "verified execution"
and even suggested successful suppression, while the structured evidence
contract still reported execution `checked-unverified`.
Neither the *actual configured value* nor prevention of an eligible
motion-triggered ON had been established. Both app log excerpts relied on
the backend app filter instead of independent per-row app IDs. This is not
just an answer wording problem: the model did not have a typed representation
of report provenance, quantity agreement and observed downstream effect.

## Cross-domain evidence architecture

The new `decision_claim_reconciliation.py` converts already-collected,
redacted app log excerpts into a separate, source-grounded **decision report**
and **effect verification** graph:

- Parse real numeric and spelled-out duration quantities into seconds, while
  retaining the original magnitude and units. Do not reinterpret 300 minutes
  as three minutes or 300 seconds.
- Compare the requested duration with each source-reported duration and expose
  explicit typed numeric differences, without presuming the user's request is
  independently verified configuration.
- Carry source-row IDs, app identity quality (explicit vs backend-filter-only),
  timestamp-offset validity and milliseconds relative to the focal event.
- Distinguish a textual decision declaration from independent proof that an
  eligible later action was actually blocked. A log's statement is an
  observation *of what the log says*, not proof of the claimed effect.
- Publish **count/quantity/type only**, never raw log messages, in technical
  `decisionClaimReconciliation` and `investigation_coverage.decisionClaimEvidence`.
  The existing bounded log packet to the reasoning model remains redacted
  and restricted to the current request.
- Focus historical lockout synthesis on the **focal event and decision**,
  avoiding irrelevant full-day light-on tables and duplicate totals unless
  that usage is explicitly requested.

## Tests

New generic unit/claim tests cover a three-minute request versus 300 minutes,
matched durations with explicitly identified app logs, missing or offsetless
timestamps, no genuine declaration, an unrelated watchdog timeout case,
sensitive log text exclusion, typed API evidence completeness, and the focal
investigation's synthesis scope.

## Limitations and safety

This does not identify an actual configured lockout duration. If source log
rows continue to say 300 minutes, investigate configuration/code separately
before changing any values. A decision being reported does not establish
that a specific motion ON attempt was suppressed.

Read-only; no device or automation writes, new scheduled calls, new hub-wide
scans, or changes to Historical Journal retention (7 days / 200,000 rows).

## Live check

After updating to 0.17.43, repeat the exact app-4019 manual-OFF lockout
query. Inspect `decisionClaimReconciliation` for the reported/requested
duration conflict, `decisionStage` for separately qualified evidence, and
`investigation_coverage` for the still-unverified effective suppression.
Provide Copy technical to check that synthesis does not silently turn a
log declaration into proof of effective inhibition.
