# CLAUDE.md

Guidance for Claude Code sessions in this repository. Read this before making
changes; it exists so you don't have to be re-briefed each session.

## What this repo is

`HomeBrainOS` is a Home Assistant add-on for a Hubitat-based smart home. The
only maintained component is `hubitat-mcp-ai/` — a native Ollama
function-calling bridge to a Hubitat MCP Rule Server. The legacy Maker-API
dashboard (`homebrainos/`, `backend/`, `frontend/`) is retired; don't build on
it, and treat any reference to it in older docs as historical.

Full architecture: `docs/ARCHITECTURE.md`. Current module-by-module map,
kept in sync with the actual runtime via a CI-enforced test: `docs/RUNTIME-MODULE-MAP.md`.

## Before writing any code

Read `CONTRIBUTING.md` in full — it is short and load-bearing, not
boilerplate. The two rules that matter most:

1. **Change the existing module, don't create a variant.** No `_v2`,
   `_fixed`, `_final`, `_safe` files. Before adding a new module under
   `hubitat-mcp-ai/rootfs/app/`, check `docs/ARCHITECTURE.md`, run
   `python scripts/analyze_imports.py`, and confirm the capability doesn't
   already exist in a live module family.
2. **Gate behavior on the actual tool call, never on prompt wording.**
   Read vs. mutation, effect classification, confirmation requirements —
   all of it comes from the declared tool name and structured arguments.
   Nothing in this codebase should do keyword/regex matching on raw user
   text to decide what's safe. This is the single most consistently
   enforced architectural rule in the project; violating it is the fastest
   way to get a change rejected.

## Local validation — run before every commit

```bash
python scripts/validate_addon.py          # repo layout + version alignment
python scripts/validate_release_consistency.py   # only if you touched a version/changelog
python scripts/analyze_imports.py          # confirms zero orphan modules
python -m pytest -q                        # full suite, currently 512 tests
```

All four should be clean before you propose a commit. `analyze_imports.py`
printing anything under `orphan_modules` means a module was added but never
wired in — that's a real defect, not noise.

## Versioning and changelogs

Every merged change to `hubitat-mcp-ai/` bumps the version. Four places must
move together — `validate_release_consistency.py` enforces this in CI:

- `hubitat-mcp-ai/config.yaml` (`version:` field)
- `README.md` (component table row)
- `hubitat-mcp-ai/README.md` ("Current add-on version" line)
- `hubitat-mcp-ai/CHANGELOG-<version>.md` (new file, one per version — see
  any existing one for the expected shape: `## Changed` / `## Validation`)
- Also update `hubitat-mcp-ai/CHANGELOG-INDEX.md`'s "Current release" pointer

**Check `origin/main` for the current version immediately before picking a
number.** Multiple agents/branches have independently claimed the same next
version more than once (e.g. 0.10.334 and 0.10.335 were each used for two
unrelated changes before the collision was caught at merge time). If you're
working from a stale local checkout, `git fetch origin main` first.

## Branch and commit conventions

- Branch names: `agent/<short-description>` for refactors and feature work,
  `ci/<short-description>` for workflow-only changes. Match the existing
  pattern in recent history (`git log --oneline -20` on `main`) rather than
  inventing a new scheme.
- Commit messages: imperative mood, `type: summary` (`refactor:`, `chore:`,
  `fix:`, `ci:`, `docs:`), with a body explaining *why* when the diff isn't
  self-explanatory — especially for extractions, explain what was verified
  unchanged and what wasn't.
- Every extraction or refactor commit should state what was actually run to
  confirm no behavior changed, not just "tests pass."

## CI

Three workflows run on every push/PR to `main`: `Validate HomeBrain OS`,
`Release assurance`, `Hubitat MCP AI tests`. As of this writing, only
`Release assurance` and `dependency-audit.yml` have
`concurrency: cancel-in-progress` groups; `validate.yml` and
`hubitat-mcp-ai-tests.yml` do not, which caused a runner-starvation incident
(stale queued runs from superseded commits starved newer runs, including an
unrelated job, of runners for 15 minutes before cancellation). A fix exists
on branch `ci/queue-starvation-concurrency-groups` — check whether it's
merged before assuming this is fixed; if not, and you see a job fail with
zero steps run and no runner assigned (`runner_id: 0` in the Actions API),
that's this same issue recurring, not a code regression in whatever was just
merged.

## Test suite shape

- `tests/test_architecture_module_map.py` fails if a runtime module isn't
  documented in `RUNTIME-MODULE-MAP.md`, or if a documented module no longer
  exists. Keep both in sync in the same commit as any module add/remove.
- `tests/test_release_assurance.py` and `tests/test_repository_hygiene.py`
  are part of the release-blocking gate (`scripts/run_release_gate.py`),
  not optional extras.
- New modules extracted from `mcp_agent_orchestrator.py` (the largest
  runtime file — track its line count; it should trend down, not up)
  should get their own dedicated test file mirroring the style of
  `tests/test_tool_catalog_assembly.py` or
  `tests/test_rule_proposal_confirmation.py`: direct unit tests against the
  extracted class/function with real dependencies, not mocks of the whole
  orchestrator.

## What NOT to do

- Don't add a module that duplicates an existing pattern without checking
  for one first — `request_lifecycle_context.py` was removed as dead code
  after being added standalone and never wired in; `DirectOutcomeContext`
  already covered its use case.
- Don't claim CI passed without having actually run it (CONTRIBUTING.md is
  explicit about this).
- Don't bypass the confirmation/grounding policies to make a feature "just
  work" — `hub_manage_rule_machine` writes, evidence-backed live claims, and
  sensitive-action confirmation are safety boundaries, not friction to
  route around.
