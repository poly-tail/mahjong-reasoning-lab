# Project Guide Template

Describe what this repository is for and what it intentionally does not contain.

## Scope
- This repository does include:
  - `documentation governance`
  - `repo contract files`
  - `maintenance scripts`
  - `validation and CI entrypoints`
- This repository does not include:
  - `project-specific business logic`
  - `runtime dependency configuration`
  - `framework-specific starter code`

## Main Flow
1. `copy or initialize the repository`
2. `rewrite AGENTS.md, README.md, and docs/context.md`
3. `update requirements/specs/screen current pointers`
4. `choose whether a language pack is needed`
5. `run validation and tests`

## Codex-Native Layer
- `AGENTS.md`: `repo contract`
- `.codex/config.toml`: `repo-local defaults`
- `.agents/skills/`: `repeatable maintenance workflows`
- `scripts/`: `cross-platform command implementation`
- `Makefile`: `local shorthand`
- `.github/workflows/ci.yml`: `automated checks`

## Base Workspace vs Language Pack
- Base workspace:
  - `repo contract`
  - `documentation structure`
  - `generic maintenance tooling`
  - `validation and CI scaffold`
- Language pack:
  - `runtime dependencies`
  - `formatter/linter config`
  - `packaging metadata`
  - `framework-specific bootstrapping`

## Documentation Governance
- Versioned product docs live next to `current.md` pointer files.
- `docs/changelog.md` records reusable template updates and migration notes.
- `docs/source_overview.md` and `docs/folder_structure.md` change together when boundaries move.
- `docs/src_call_graph.md` and `docs/graphs/src/*.mmd` are the graph sources of truth.

## Tooling Placement
- Put repeatable maintenance commands in `scripts/`.
- Keep `cli/` thin.
- Put project-specific preview, export, or batch tools in the project's app layer.
- Keep one-off investigative outputs in `analysis_output/`.

## Best Practices
- Keep the base workspace small and generic.
- Remove stale generated artifacts instead of documenting around them.
- Prefer explicit command entrypoints over long README-only shell snippets.
