# Documentation-First Base Workspace Template

`template_workspace/` is a reusable base workspace for Codex-assisted projects.

It is intentionally not a full application starter.
The base template focuses on:
- repo structure
- documentation governance
- Codex operating contract
- cross-platform maintenance scripts
- validation and CI entrypoints

Runtime- or stack-specific files should be layered in only after the project chooses a language or framework.

## Included Codex-Native Layers
- `AGENTS.md`: repo layout, commands, constraints, done criteria.
- `.codex/config.toml`: repo-local Codex defaults.
- `.agents/skills/`: repeatable maintenance workflows.
- `scripts/`: cross-platform helpers for validation, graph rendering, and cache cleanup.
- `Makefile`: simple command entrypoints.
- `.github/workflows/ci.yml`: validation + unit-test example for new repos.

## Quick Start
1. Copy `template_workspace/` into a new repository.
2. Replace placeholders such as `PROJECT_NAME`, dates, and version numbers.
3. Update `AGENTS.md`, `README.md`, and `docs/context.md` for the new project.
4. Decide whether the repo stays base-only for a while or adopts a language pack.
5. Run:
   - `python scripts/validate_workspace.py`
   - `python -B -m unittest discover -s tests/unit -p "test_*.py"`

## Canonical Commands
- Validate workspace structure: `python scripts/validate_workspace.py`
- Run unit tests: `python -B -m unittest discover -s tests/unit -p "test_*.py"`
- Dry-run Mermaid rendering: `python scripts/render_docs_graphs.py --dry-run`
- Render Mermaid graphs: `python scripts/render_docs_graphs.py`
- Remove Python cache artifacts: `python scripts/clean_python_cache.py`
- Combined local check: `make check`

## Base Workspace vs Language Pack
- Base workspace:
  - `docs/`
  - `AGENTS.md`
  - `.codex/config.toml`
  - `.agents/skills/`
  - `scripts/`
  - `Makefile`
  - CI scaffolding
- Language pack:
  - runtime dependencies
  - lint/test tool configuration
  - packaging metadata
  - framework-specific bootstrapping

See [language_packs/README.md](./language_packs/README.md) and [language_packs/python/README.md](./language_packs/python/README.md).

## Purity Rules
- Do not ship `__pycache__/` or `*.pyc`.
- Do not ship generated Mermaid SVGs in the template. Keep only `docs/graphs/generated/README.md`.
- Keep `cli/` thin. Put reusable logic in `scripts/` or `src/app/`.
- Avoid project-specific business examples in the base template.

## Main Docs
- [docs/README.md](./docs/README.md)
- [docs/context.md](./docs/context.md)
- [docs/project_guide.md](./docs/project_guide.md)
- [docs/source_overview.md](./docs/source_overview.md)
- [docs/folder_structure.md](./docs/folder_structure.md)
- [docs/src_call_graph.md](./docs/src_call_graph.md)
- [docs/changelog.md](./docs/changelog.md)

## 2026-04-11 Template Update Notes
- Added `AGENTS.md`, `.codex/config.toml`, and repeatable Codex skills.
- Added cross-platform `scripts/` and `Makefile` command entrypoints.
- Added CI scaffold under `.github/workflows/ci.yml`.
- Split stack-specific guidance into `language_packs/`.
- Removed `__pycache__/` and generated Mermaid SVGs from the shipped template.
