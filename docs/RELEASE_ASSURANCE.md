# Release assurance

Every pull request and push to `main` runs the staged `Release assurance` workflow.

## Required checks

- **Metadata and repository validation** checks version consistency, add-on structure, the maintained import graph, repository hygiene, safe ingress defaults, and Python compilation.
- **Full Python test suite** runs the blocking repository release gate.
- **Add-on container smoke test** builds the Home Assistant add-on image, compiles the packaged runtime, verifies the embedded build version, and confirms the startup script is executable.

The workflow cancels superseded runs for the same branch so outdated revisions do not consume CI capacity or obscure the current result.

## Local commands

```bash
python scripts/validate_release_consistency.py
python scripts/validate_addon.py
python scripts/analyze_imports.py
python scripts/run_release_gate.py
```

Before merging, configure branch protection for `main` to require all three named jobs and require the branch to be up to date. The repository settings are intentionally not changed by this code-only pull request.
