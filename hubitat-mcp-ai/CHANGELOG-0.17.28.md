# HomeBrain 0.17.28 — Protect focal event investigations from global audit routing

## Live regression

HomeBrain 0.17.27 answered a read-only question about why Bedroom 1 Light
switched OFF at 17:14:05 on 12 October 2026 by running a
`comprehensive-system-audit` (40.5 seconds; 214 devices, 152 automations,
200 generic logs), instead of using the historical journal and focal MCP
evidence. No lighting-cause investigation was performed.

## Root cause

`automation_diagnostic_policy.is_broad_automation_runtime_diagnostic`
previously interpreted generic words (`which`, `any`, `all`, `system`)
anywhere in a prompt as a broad audit signal. The phrase "which history
source supports each conclusion" inadvertently activated this gate because
the same request also contained "Investigate" and "automation evidence".
The general System Check shortcut could also swallow targeted causal
questions mentioning both device history and app logs.

## Correction

- Only choose broad automation diagnostics when the prompt explicitly
  requests a population of automations/rules/apps or whole-hub scope.
- Protect a specifically timed, named ON/OFF device investigation even if
  automation evidence, app logs, or the word `which` is included. These
  prompts must proceed to the existing causal investigative agent.
- Preserve explicit comprehensive System Check requests and genuinely broad
  automation investigations.
- Regression tests cover the exact live request, alternative named
  device/event phrasing, false broad-scope words and true broad audits.
- This is routing only. The 0.17.27 journal-first causal collector, 7-day
  retention, 200,000-row configuration, Hubitat devices and rules are not
  changed.

## Live follow-up

After upgrading, repeat the **same** Bedroom 1 Light OFF question.
Expected route: `unified-mcp-agent`, not `comprehensive-system-audit`.
Check `journalFirstPlan` and `focalWindowRetrieval` in the detailed JSON.
An unresolved OFF cause is acceptable if no authoritative command evidence
was retained; an unrelated full-system audit is not.
