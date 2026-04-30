# Folder Structure

```text
PROJECT_NAME/
|-- .agents/
|   `-- skills/
|       |-- sync-current-files/
|       |   `-- SKILL.md
|       `-- update-docs/
|           `-- SKILL.md
|-- .codex/
|   `-- config.toml
|-- .github/
|   `-- workflows/
|       `-- ci.yml
|-- AGENTS.md
|-- Makefile
|-- README.md
|-- analysis_output/
|   `-- README.md
|-- assets/
|   |-- README.md
|   `-- samples/
|       `-- README.md
|-- cli/
|   |-- README.md
|   `-- render_docs_graphs.ps1
|-- docs/
|   |-- README.md
|   |-- analysis/
|   |   `-- README.md
|   |-- changelog.md
|   |-- context.md
|   |-- folder_structure.md
|   |-- graphs/
|   |   |-- generated/
|   |   |   `-- README.md
|   |   `-- src/
|   |       |-- project_flow.mmd
|   |       `-- project_hierarchy.mmd
|   |-- project_guide.md
|   |-- requirements/
|   |   |-- current.md
|   |   `-- requirements_v1.0.md
|   |-- screen_specs/
|   |   |-- change_request.md
|   |   |-- current.md
|   |   |-- invariants.md
|   |   |-- screen_map.md
|   |   |-- screen_spec_v1.0.md
|   |   `-- ui_principles.md
|   |-- source_overview.md
|   |-- specs/
|   |   |-- api_spec_v1.0.md
|   |   `-- current.md
|   |-- src_call_graph.md
|   |-- templates/
|   |   |-- api_spec_template.md
|   |   |-- changelog_template.md
|   |   |-- context_template.md
|   |   |-- current_doc_template.md
|   |   |-- folder_structure_template.md
|   |   |-- project_guide_template.md
|   |   |-- requirement_template.md
|   |   |-- screen_spec_template.md
|   |   |-- source_overview_template.md
|   |   |-- src_call_graph_template.md
|   |   `-- troubleshooting_note_template.md
|   `-- troubleshooting/
|       `-- README.md
|-- language_packs/
|   |-- README.md
|   `-- python/
|       `-- README.md
|-- logs/
|   `-- README.md
|-- scripts/
|   |-- README.md
|   |-- clean_python_cache.py
|   |-- render_docs_graphs.py
|   `-- validate_workspace.py
|-- src/
|   |-- README.md
|   |-- app/
|   |   `-- README.md
|   |-- domain/
|   |   `-- README.md
|   |-- infrastructure/
|   |   `-- README.md
|   |-- shared/
|   |   `-- README.md
|   `-- ui/
|       `-- README.md
`-- tests/
    |-- README.md
    |-- fixtures/
    |   `-- README.md
    |-- integration/
    |   `-- README.md
    `-- unit/
        |-- README.md
        `-- test_workspace_structure.py
```

## Notes
- `AGENTS.md` is the main repo contract.
- `.codex/` and `.agents/skills/` hold Codex-specific configuration and repeatable workflows.
- `scripts/` contains cross-platform command implementations.
- `cli/` stays thin and should mostly delegate to `scripts/`.
- `docs/graphs/generated/` is local-output only. The shipped template keeps the README and source `.mmd` files.
- `language_packs/` is where stack-specific overlays are staged before adoption.

## Update Rules
- When directory ownership changes, update `docs/source_overview.md`.
- When command entrypoints change, update `README.md` and `AGENTS.md`.
- When graph policy changes, update `docs/src_call_graph.md` and `docs/changelog.md`.
