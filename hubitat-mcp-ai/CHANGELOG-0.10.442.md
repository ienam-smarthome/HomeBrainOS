# Hubitat MCP AI 0.10.442

## Exact preflight failures and targeted resolution

- Classify exhausted Rule Machine proposal validation as a failed request instead of displaying a green Success outcome.
- Return the exact validation reason and rejected structured payload when the model does not correct a malformed proposal.
- Allow one bounded correction round, then stop instead of spending up to ten model rounds on an invalid write.
- Resolve named devices through a projected `labelFilter` lookup rather than reading all 124 devices before every targeted operation.
- Record targeted resolution evidence separately and do not describe an unmatched targeted lookup as a complete inventory scan.
- Add regression coverage for failed outcome presentation, rejected-payload visibility, bounded retry, and targeted resolution contracts.
