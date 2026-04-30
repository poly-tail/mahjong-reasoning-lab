# Changelog

## Rules
- Record reusable template guidance as addenda.
- Record repo-contract, command-entrypoint, and generated-artifact policy changes here.
- Keep project-specific business examples out of the base template changelog.

## 2026-04-11 Addendum
- `CH-006`: added `AGENTS.md`, `.codex/config.toml`, and `.agents/skills/` to make the Codex-facing repo contract explicit
- `CH-007`: added cross-platform scripts, `Makefile`, CI, and a validation test scaffold
- `CH-008`: split base workspace guidance from stack-specific `language_packs/`
- `CH-009`: removed `__pycache__/` and generated Mermaid SVGs from the shipped template

## 2026-04-10 Addendum
- `CH-005`: removed domain-specific hand-preview tooling from the template and clarified project-side placement rules
- `CH-004`: generalized tooling-placement guidance in `project_guide`
- `CH-003`: reverted same-day domain-specific preview examples from the template
- `CH-002`: added reusable UI alert and derived-metric guidance to the template

## YYYY-MM-DD Addendum
- `CH-001`: initial workspace template created

| Date | Change ID | Type | Summary | Author | Files |
|------|-----------|------|---------|--------|-------|
| 2026-04-11 | CH-009 | cleanup | removed `__pycache__/` and generated Mermaid SVGs from the shipped template | codex | `src/app/__pycache__/` `tests/unit/__pycache__/` `docs/graphs/generated/project_flow.svg` `docs/graphs/generated/project_hierarchy.svg` `docs/changelog.md` |
| 2026-04-11 | CH-008 | docs | split base workspace and language-pack guidance | codex | `README.md` `language_packs/README.md` `language_packs/python/README.md` `docs/project_guide.md` `docs/folder_structure.md` `docs/changelog.md` |
| 2026-04-11 | CH-007 | tooling | added cross-platform scripts, Makefile, CI, and template validation test | codex | `Makefile` `scripts/*` `.github/workflows/ci.yml` `tests/unit/test_workspace_structure.py` `docs/src_call_graph.md` `docs/changelog.md` |
| 2026-04-11 | CH-006 | docs | added Codex-native contract files and repeatable skills | codex | `AGENTS.md` `.codex/config.toml` `.agents/skills/*` `README.md` `docs/context.md` `docs/project_guide.md` `docs/changelog.md` |
| 2026-04-10 | CH-005 | docs | removed domain-specific hand-preview tooling from template workspace and clarified project-side placement rules | codex | `README.md` `cli/README.md` `src/app/README.md` `docs/source_overview.md` `docs/folder_structure.md` `docs/project_guide.md` `docs/templates/project_guide_template.md` `docs/changelog.md` |
| 2026-04-10 | CH-004 | docs | generalized tooling placement and responsibility split | codex | `docs/project_guide.md` `docs/templates/project_guide_template.md` `docs/changelog.md` |
| 2026-04-10 | CH-003 | docs | reverted same-day domain-specific preview examples from the template | codex | `docs/changelog.md` |
| 2026-04-10 | CH-002 | docs | added reusable UI alert and derived-metric guidance | codex | `README.md` `docs/project_guide.md` `docs/templates/project_guide_template.md` `docs/changelog.md` |
| YYYY-MM-DD | CH-001 | docs | initial workspace template created | name | `path/to/file` |
