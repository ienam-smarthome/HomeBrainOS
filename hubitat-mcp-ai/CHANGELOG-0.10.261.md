# Hubitat MCP AI 0.10.261

- Remove orphan `device_health_service.py`; live device-health reporting is already handled by the active deterministic device-query and home-snapshot paths.
- Remove orphan `home_summary_presenter.py`; live home summaries are already rendered by the active deterministic presenter.
- Keep the flat runtime package free of zero-importer modules.
- Align both README version references with the add-on version.
