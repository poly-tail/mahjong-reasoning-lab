# Project Guide

This repository is a reusable base workspace, not a full application starter.

## Scope
- This template does include:
  - documentation governance
  - Codex operating contract files
  - cross-platform maintenance scripts
  - validation and CI entrypoints
- This template does not include:
  - project-specific business logic
  - runtime dependency configuration
  - framework-specific starter code

## Main Flow
1. Copy the workspace into a new repository.
2. Rewrite `AGENTS.md`, `README.md`, and `docs/context.md` for the new project.
3. Update `docs/requirements/current.md`, `docs/specs/current.md`, and `docs/screen_specs/current.md`.
4. Decide whether the repo stays base-only for a while or adopts a language pack.
5. Run `python scripts/validate_workspace.py` and the template unit tests.

## Codex-Native Layer
- `AGENTS.md`: repo layout, commands, constraints, and done criteria
- `.codex/config.toml`: repo-local Codex defaults
- `.agents/skills/`: repeatable doc-sync and pointer-sync workflows
- `scripts/`: cross-platform command implementations
- `Makefile`: short local entrypoints
- `.github/workflows/ci.yml`: baseline automated checks

## Base Workspace vs Language Pack
- Base workspace:
  - repository contract
  - documentation structure
  - generic maintenance tooling
  - validation and CI scaffold
- Language pack:
  - runtime dependencies
  - formatter and linter configuration
  - packaging metadata
  - framework-specific bootstrapping

Keep runtime-specific files out of the base workspace until a project explicitly chooses them.

## Documentation Governance
- Versioned product docs live next to `current.md` pointer files.
- `docs/changelog.md` records reusable template updates and migration notes.
- `docs/source_overview.md` and `docs/folder_structure.md` are updated together when ownership boundaries move.
- `docs/src_call_graph.md` and `docs/graphs/src/*.mmd` are the canonical graph sources.

## Tooling Placement
- Put repeatable maintenance commands in `scripts/`.
- Keep `cli/` as a thin wrapper layer.
- Put project-specific preview, export, or batch tools in the project's `src/app/` or app-specific CLI layer.
- Keep one-off investigative outputs in `analysis_output/`.

## Template Best Practices
- Keep the base workspace small and generic.
- Remove stale generated artifacts instead of documenting around them.
- Prefer explicit command entrypoints over long README-only shell instructions.
- Treat language packs as overlays, not as hidden assumptions baked into the template.
