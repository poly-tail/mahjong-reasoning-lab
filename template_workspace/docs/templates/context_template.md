# Project Context Template

## Overview
- Project name: `PROJECT_NAME`
- Repository role: `documentation-first base workspace`, `application repo`, or `library repo`
- Primary goal: `describe the repo mission in one sentence`

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
- Change history: `docs/changelog.md`

## Codex-Native Layers
- `AGENTS.md`: `repo contract`
- `.codex/config.toml`: `repo-local Codex defaults`
- `.agents/skills/`: `repeatable workflows`
- `scripts/`: `cross-platform maintenance commands`
- `.github/workflows/ci.yml`: `baseline automation`

## Maintenance Rules
- Update each `current.md` pointer with the linked versioned document.
- Update `docs/source_overview.md` and `docs/folder_structure.md` together when ownership changes.
- Update `README.md`, `AGENTS.md`, and `docs/project_guide.md` when command entrypoints change.
- Update `docs/src_call_graph.md` and `docs/graphs/src/*.mmd` when graph meaning or graph policy changes.

## Documentation Areas
- `docs/`: `canonical docs`
- `docs/analysis/`: `analysis notes`
- `docs/troubleshooting/`: `operational recovery notes`
- `docs/templates/`: `document skeletons`
- `language_packs/`: `stack-specific overlays, if this repo uses the base-workspace pattern`

## Purity Rules
- Do not commit `__pycache__/` or `*.pyc`.
- Do not treat generated SVGs as source files.
- Keep stack-specific files out of the base workspace until the project explicitly adopts them.
