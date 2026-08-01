# Hubitat MCP AI 0.10.290

## Architecture

- Adds a request-local `LiveEvidenceAuthority` that combines evidence receipts
  with the existing bounded grounding policy.
- Gives one component responsibility for accepting a grounded answer, issuing
  the single permitted retry, or returning the deterministic refusal.
- Keeps prompt routing, tool execution, receipt mutation, and provider transport
  outside the authority boundary.

## Tests

- Proves tool discovery alone cannot authorize a live-state answer.
- Proves successful live receipts permit answers, log requests require a
  successful authoritative log call, and conversational replies remain exempt.
