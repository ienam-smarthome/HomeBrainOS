# Hubitat MCP AI 0.10.440

## Required-expression fail-closed verification

- Reject unsupported required-expression aliases and spelling variants, including the live-observed `requiredExpressions` plural field, before confirmation.
- Accept only the documented `addRequiredExpression` and `replaceRequiredExpression` operation names, with shapes obtained from live discovery.
- Do not treat a rule ID and `health.ok=true` as proof that a requested required expression was saved.
- Require an explicit `requiredExpressionApplied=true` acknowledgement before reporting a required-expression write as verified; otherwise report it as unverified for direct inspection.
- Add regression coverage for the second Big Lamp false-success payload and the stricter semantic verification boundary.
