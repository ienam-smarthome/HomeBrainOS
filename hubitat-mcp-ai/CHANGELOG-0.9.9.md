# 0.9.9

- Retry targeted device resolution against the plain authoritative inventory when a
  schema-valid field projection returns no searchable labels or matches.
- Record projected and final inventory counts plus the successful search strategy.
- Reject false model claims that the device inventory timed out when MCP completed
  successfully.
- Fall back to HomeBrain's grounded automation recommendation service when final
  synthesis refuses a recommendation despite valid device evidence.
