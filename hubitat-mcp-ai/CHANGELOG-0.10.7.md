# 0.10.7

- Recognises combined requests such as `Suggest one useful automation for the
  devices I have and write a rule` as grounded automation recommendations.
- Uses the verified Hubitat inventory and stores the recommendation for the safe,
  review-first rule workflow.
- Replaces false missing-device-list claims after successful MCP inventory reads.
- Keeps recommendation matching terminal outside the unified AI planner while
  preserving the pending recommendation used by the safe rule-draft workflow.
