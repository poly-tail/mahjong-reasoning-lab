# python language pack

This is an optional overlay for Python projects.

## Typical Additions
- `pyproject.toml`
- formatter/linter config such as Ruff or Black
- test runner config such as `pytest.ini`
- Python-specific CI steps
- packaging or CLI entrypoints

## Keep in the Base Workspace
- `AGENTS.md`
- `.codex/config.toml`
- `.agents/skills/`
- `docs/`
- `scripts/` that are purely repo-maintenance helpers

## Move into the Project Once Python Is Chosen
- runtime dependencies
- app-specific tooling configuration
- packaging metadata
- environment bootstrapping rules
