# Project Context

## Overview
- Project name: `PROJECT_NAME`
- Repository role: documentation-first base workspace for Codex-assisted projects
- Primary goal: establish a reusable repo contract before runtime-specific code is added

## Read First
- `AGENTS.md`
- `README.md`
- `docs/README.md`
- `docs/project_guide.md`
- `docs/source_overview.md`
- `docs/folder_structure.md`

## Canonical Product Docs
- Current requirements: `docs/requirements/current.md`
- Current API/spec contract: `docs/specs/current.md`
- Current screen contract: `docs/screen_specs/current.md`
- Template change history: `docs/changelog.md`

## Codex-Native Layers
- `AGENTS.md`: repository contract, commands, constraints, and done criteria
- `.codex/config.toml`: repo-local Codex defaults
- `.agents/skills/`: repeatable maintenance workflows
- `scripts/`: cross-platform maintenance commands
- `.github/workflows/ci.yml`: baseline validation and test automation

## Maintenance Rules
- When a `current.md` pointer changes, update the linked versioned document in the same change.
- When repository structure or ownership changes, update `docs/source_overview.md` and `docs/folder_structure.md` together.
- When command entrypoints change, update `README.md`, `AGENTS.md`, and `docs/project_guide.md`.
- When graph sources or graph policy change, update `docs/src_call_graph.md`, `docs/graphs/src/*.mmd`, and `docs/changelog.md`.

## Documentation Areas
- `docs/`: canonical project documentation
- `docs/analysis/`: reusable analysis notes
- `docs/troubleshooting/`: operational recovery notes
- `docs/templates/`: document skeletons for new repos or new versions
- `language_packs/`: stack-specific overlays kept separate from the base workspace

## Template Purity Rules
- Do not commit `__pycache__/` or `*.pyc`.
- Do not ship generated Mermaid SVGs in the template. Keep only `docs/graphs/generated/README.md`.
- Keep stack-specific runtime choices out of the base workspace until the project chooses a language pack.
- Keep reusable repo operations in `scripts/` rather than documenting one-off shell snippets only in Markdown.
