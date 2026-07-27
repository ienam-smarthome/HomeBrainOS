# GitHub Workflow

HomeBrainOS uses GitHub Actions to validate the repository and package the Hubitat MCP AI add-on.

## Validation

Every push and pull request to `main` runs:

- Home Assistant add-on file checks
- `config.yaml` validation
- Python syntax compilation

## Release package

To create a package manually:

1. Go to **Actions**.
2. Select **Package Hubitat MCP AI add-on**.
3. Click **Run workflow**.
4. Download the generated `hubitat-mcp-ai-addon` artifact.

Later we can turn this into full GitHub Releases and Home Assistant repository updates.
