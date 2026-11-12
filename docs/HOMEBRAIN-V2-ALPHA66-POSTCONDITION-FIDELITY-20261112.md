# HomeBrainOS V2 alpha.66 — postcondition fidelity and temporal intent

**Date:** 12 November 2026. **Scope:** one general native MCP result interpretation improvement plus model-led temporal-action reasoning. **Installed live acceptance:** pending. No live tool calls, router changes, household identifiers or private receipts in repository fixtures.

## Observed evidence and failure modes

A private alpha.65 timed-control attempt issued an advertised native delayed command, and the original server receipt returned `success=true` plus a fresh future deadline and matching duration. The same reply had a nested `waitFor` report (`converged=false`, `timedOut=true`, unchanged final value, about five seconds spent). That optional wait checked an attribute whose semantics were never demonstrated to represent the requested timer. The first answer rightly described the pending target deadline but silently omitted the failed secondary check. Separate user-supplied Hubitat logs later showed the driver fired and reported applying the change, but independent network/device connectivity was not measured by that first answer.

An adjacent private request asked to start the opposite action **after** two minutes. The model selected a native `allowForMinutes(2)` operation, whose contemporaneous receipt already reported access **allowed now**, not an operation scheduled to start after two minutes. The model's first draft called this delayed onset and its review only changed the claim to “allowed for two minutes,” not the mismatch with the user's goal. Any future re-block after that allowance would need its own authoritative receipt; no such future execution is proved by the original call.

These are general defects in **postcondition meaning**, **nested verification reporting**, and **temporal operators**. A command that starts now FOR an interval is not a command that starts AFTER the interval. Do not patch specific devices or command strings.

## Implemented change

- General skill guidance distinguishes `after/in` (delayed start), `for` (temporary immediate interval), `until` (end deadline), and `every` (recurrence), while requiring authoritative command semantics rather than guessing from a label. If a matching delayed operation is not supported, do not silently change the action immediately or invent a scheduler.
- For optional native `waitFor` or read polling, choose a postcondition with grounded attribute semantics. When semantics are unknown, omit the blocking wait and consider a proportional read-only target readback instead. Do not use an unrelated `remaining`, `schedule`, or `status` attribute just because its name sounds relevant.
- Add a small source-bounded `client_native_wait_for_scope` to the **model's copy of the original MCP result**. It exposes the exact native nested `waitFor` outcome and top-level domain `success` separately, labels the optional convergence outcome as `converged`, `not_converged`, `timed_out` or `unknown`, and explicitly disclaims independent proof. The original native response is retained untouched alongside it; no new MCP read or validation action is executed automatically.
- Private first-answer telemetry records `native_wait_for_outcome` on the same original tool receipt, independently of the top-level MCP transport success. This supports retrospective first-answer evaluation without exposing household details.
- Extend the existing single model-led read-only action-outcome review to **disclose** material nested failed checks and to compare the timing of the action actually executed with the user's requested onset, duration, recurrence or cutoff. The review still cannot make corrective writes, and the model owns the answer.

## Synthetic tests and limits

The fictional regression suite checks a successful deferred command alongside a timed-out optional wait, convergence versus non-convergence, missing/non-JSON nested receipts, gateway argument form, preservation of the original payload, and a scripted live agent loop in which:
- the model notes both a stored future deadline and an unrelated failed wait;
- a model-selected immediate temporary operation is explicitly rejected as proof of a requested delayed start;
- no extra device write or automatic fix occurs during the read-only review.

No forced tool selection, no invented native scheduling layer, no automatic retry or cancellation, no device-specific hardcoding and no V1 changes. The synthetic tests prove evidence is accessible and the review opportunity exists; they **do not prove** Gemma chooses correct `waitFor` or temporal semantics first time.

## Required acceptance

Validate exact PR-head workflows and the post-merge release gates. Install alpha.66 and perform a **read-only first-answer semantic comparison** using a new fictional or low-impact driver-capability example: ask whether “after N minutes” can be fulfilled with only a native “for N minutes” command, and verify that the model declines to claim delayed onset without a matching server-owned schedule. Separately assess that any future accepted command receipt with nested `waitFor.timedOut=true` is explicitly reported as a *failed verification*, not as an action failure and not silently omitted.

Never live-test power/security/internet effects without separately approved user intent. The previous delayed-control test logs establish the driver's reported execution, not independent router/network enforcement.
