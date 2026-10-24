# HomeBrainOS 0.18.101 — One AI investigation objective, fewer word routers

## Problem

As of 0.18.100, HomeBrain could successfully answer a straightforward TV-on duration question (accurate switch history, ON/OFF table, overnight carry-over and open interval) while complex investigations still contained competing keyword classifiers that could reinterpret "apps", "source", "rule", "logs", "audit", "comprehensive", "history" or "automation" after the AI had already selected its objective.

## Changes

- **One AI read objective:** after the existing request-local no-tools AI interpretation has selected an objective, the read-only investigation eligibility and source-code evidence classifier now follow that objective rather than rerunning legacy word clusters. The legacy fallback only applies when no interpreted objective is available.
- **Rule instance investigations receive interpretation:** a named app/rule read-only diagnostic can be interpreted by the same AI routing step instead of being excluded by its lexical rule reference. Explicit installed-rule investigation remains a model-led interactive MCP read (not a broad system audit); the host retains verified identity and permission checks.
- **Rule/design prompts respect AI scope:** where a scoped model objective exists, the orchestrator derives existing-rule verification, read-only proposal review and deep rule-logic scope from that one objective. Words like "review", "actions", "automation", or "configuration" cannot independently launch a separate diagnostic banner for a device-connectivity investigation.
- **No secondary diagnostic reclassification:** unrelated historical-event, generic automation-runtime and integration-runtime keyword checks no longer reclassify read-only investigations after an objective is established. The model still selects which allowed MCP reads to investigate.
- **Direct commands remain deterministic and safe:** explicit Turn ON/OFF, Set, and other modifying instructions are excluded from the semantic read eligibility, even if an unexpected interpretation object is present. The independent command parsing, host-level permission checks, write validation, confirmation and tool effects are unchanged. Exact "Run system check" and unequivocally scoped whole-hub report workflows retain their existing safe fast paths.
- **Regression suite:** covers arbitrary natural-language questions without the old routing keywords, contradictions between words and AI objective, source-code versus target-device intent, target-rule interpretation, request-local separation, direct command exclusions and host write safety.

## Evidence and limitations

This release addresses a documented word-routing architectural cause of wrong investigative scope. It does **not** claim Claude-equivalent root-cause reasoning: actual driver method tracing, follow-up planning, upstream verification, and synthesis must still be validated with live read-only Hubitat evidence. It avoids an extra model round for requests that do not enter the pre-existing arbitration step. No live devices, rules, settings, model tier or paid budget were modified.
