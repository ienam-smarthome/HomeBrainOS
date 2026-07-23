# Hubitat MCP AI 0.10.44

## Repository hygiene and safer onboarding

- Removed obsolete `0.10.43` release automation and temporary CI trigger files.
- Added regression coverage to prevent release-specific workflows and trigger artifacts from being committed again.
- Clarified that Hubitat MCP AI and the legacy HomeBrain OS dashboard are separate, independently versioned add-ons.
- New installations now start with rule writes disabled. Users can opt in after reviewing the guarded, paused-rule workflow.
