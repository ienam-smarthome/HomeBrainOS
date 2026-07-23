# 0.10.58

Fixes release/runtime route binding after the entrypoint split.

- Rebinds `/api/ask` after deterministic app control is installed.
- Ensures `disable Life360 app` reaches the guarded app controller instead of generic AI device search.
- Rebuilds the home page route using the current runtime release number.
- Adds no-store headers to prevent stale version headers after updates.
