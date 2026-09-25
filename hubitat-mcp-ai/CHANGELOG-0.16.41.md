# Hubitat MCP AI 0.16.41

## Fix warm causal planning for explicit empty context shape

Repeated Hallway live tests on 0.16.40 showed that the candidate planner still
fell back to a whole-home `hubitat://context` refresh even when another request
had refreshed that context only seconds earlier.

The live trace proved this was not a TTL expiry: the second request arrived about
16 seconds after the previous context read, well inside the 120-second structural
identity TTL, yet still recorded `causal_cached_candidate_plan_fallback: 1`.

The remaining gap was the distinction between **unknown attribute shape** and an
**explicitly empty attribute shape**. A complete cached context row may legitimately
contain an empty state container for a broad-capability bridge child. 0.16.40
treated both cases as unknown and therefore refreshed the whole home again.

0.16.41 preserves the exact-ID cache enrichment but records when the cached live
row explicitly supplied a state container, even if it was empty. Candidate
selection can then safely exclude that child if it exposes no motion/presence
attribute.

### Safety boundary

- Only an exact device-ID match may contribute cached attribute shape.
- The cached live-context snapshot must still pass generation and identity-TTL checks.
- An explicit empty state container is treated as known-empty; a missing state
  container remains unknown and still forces the safe live fallback.
- Cached state values are not promoted into current causal evidence.
- Command, subject, controller, and sensor histories remain live.
- Write invalidation behavior is unchanged.

### Expected Hallway retest

A repeated causal query inside the structural TTL should now show:

```text
causal_cached_candidate_plan: 1
causal_cached_context_shape_plan: 1
causal_cached_candidate_plan_fallback: 0
```

and should not perform a new whole-home `hubitat://context` read solely for
candidate discovery.

### Regression coverage

Tests now verify both sides of the boundary:

1. an exact-ID cached context row with an explicit empty state container is known
   shape and may be safely excluded from occupancy candidates;
2. an otherwise identical row with the state container missing remains unknown and
   still triggers the conservative fallback.
