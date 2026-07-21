# 0.10.2

- Route explicit hub-backup requests through a deterministic MCP workflow that reads
  the best-practice acknowledgement, sends confirmation, uses an idempotency token,
  verifies slow or timed-out operations, and prevents duplicate backup creation.
