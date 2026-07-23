# 0.10.59

Fixes stale HomeBrain Web UI shells under Home Assistant ingress.

- Replaces cache-first PWA navigation with network-only navigation.
- Deletes all historical HomeBrain shell caches during service-worker activation.
- Adds a one-time client cache reset for the new release.
- Adds `X-HomeBrain-Version` to the rendered page response.
- Keeps the guarded deterministic app-control route introduced in 0.10.57/0.10.58.
