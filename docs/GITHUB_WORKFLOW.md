# GitHub Workflow

HomeBrain OS uses GitHub Actions to validate the repository and package the Home Assistant add-on.

## Validation

Every push and pull request to `main` runs:

- Home Assistant add-on file checks
- `config.yaml` validation
- Python syntax compilation

## Release package

To create a package manually:

1. Go to **Actions**.
2. Select **Package Release**.
3. Click **Run workflow**.
4. Download the generated `homebrainos-addon` artifact.

Later we can turn this into full GitHub Releases and Home Assistant repository updates.
