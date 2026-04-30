# AGENTS.md

This repository is a documentation-first base workspace template for Codex-driven projects.
Read this file before making changes.

## Repo Layout
- `README.md`: template intent, quick start, command entrypoints, extension policy.
- `docs/`: requirements/specs/screen docs, project guide, source overview, changelog, graph sources.
- `src/`: application code split into `app`, `domain`, `infrastructure`, `shared`, and `ui`.
- `tests/`: `unit`, `integration`, and `fixtures`.
- `scripts/`: cross-platform helper scripts. Prefer these over ad-hoc shell commands.
- `cli/`: thin wrappers only. If logic grows, move it into `scripts/` or `src/app/`.
- `.agents/skills/`: repeatable Codex workflows for repo maintenance.
- `.codex/config.toml`: repo-local Codex defaults.
- `language_packs/`: optional stack-specific overlays. Keep the base workspace generic.

## Commands
- Validate workspace structure: `python scripts/validate_workspace.py`
- Run template unit tests: `python -B -m unittest discover -s tests/unit -p "test_*.py"`
- Dry-run graph rendering: `python scripts/render_docs_graphs.py --dry-run`
- Render Mermaid graphs: `python scripts/render_docs_graphs.py`
- Remove Python cache artifacts: `python scripts/clean_python_cache.py`
- Combined local check: `make check`

## Constraints
- Do not commit `__pycache__/` or `*.pyc`.
- Treat `docs/graphs/generated/*.svg` as local/generated artifacts. Edit `docs/graphs/src/*.mmd` instead.
- Keep stack-specific runtime choices out of the base template. Put them in `language_packs/` until the project chooses one.
- When adding repeatable repo workflows, prefer a script plus AGENTS/docs guidance over one-off shell instructions in README only.

## Done Criteria
- `python scripts/validate_workspace.py` passes.
- `python -B -m unittest discover -s tests/unit -p "test_*.py"` passes.
- If repo structure or commands change, update `README.md`, `docs/context.md`, `docs/project_guide.md`, `docs/source_overview.md`, and `docs/folder_structure.md`.
- If requirements/specs/screen docs change, update the matching `current.md` pointer and `docs/changelog.md`.
- If graph meaning or graph sources change, update `docs/src_call_graph.md` and `docs/graphs/src/*.mmd`.

## Review Rules
- Prefer small, explicit changes over template sprawl.
- Remove stale generated artifacts and abandoned examples instead of documenting around them.
- Keep comments and docs focused on why the structure exists, not only what a file does.

## Doc Sync Rules
- `docs/requirements/current.md`, `docs/specs/current.md`, and `docs/screen_specs/current.md` are pointers to versioned docs.
- `docs/changelog.md` records reusable template rules, not only app-specific features.
- `docs/source_overview.md` and `docs/folder_structure.md` should change together when directories or ownership boundaries move.
