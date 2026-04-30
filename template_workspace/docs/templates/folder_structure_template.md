# Folder Structure Template

```text
project_root/
|-- .agents/
|   `-- skills/
|       `-- example-skill/
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
|   `-- wrapper_example.ps1
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
|   |       `-- graph_example.mmd
|   |-- project_guide.md
|   |-- requirements/
|   |   |-- current.md
|   |   `-- requirements_v1.0.md
|   |-- screen_specs/
|   |   |-- current.md
|   |   `-- screen_spec_v1.0.md
|   |-- source_overview.md
|   |-- specs/
|   |   |-- api_spec_v1.0.md
|   |   `-- current.md
|   |-- src_call_graph.md
|   |-- templates/
|   |   `-- *.md
|   `-- troubleshooting/
|       `-- README.md
|-- language_packs/
|   `-- README.md
|-- logs/
|   `-- README.md
|-- scripts/
|   |-- README.md
|   |-- clean_python_cache.py
|   |-- render_docs_graphs.py
|   `-- validate_workspace.py
|-- src/
|   |-- app/
|   |-- domain/
|   |-- infrastructure/
|   |-- shared/
|   `-- ui/
`-- tests/
    |-- fixtures/
    |-- integration/
    `-- unit/
```

## Notes
- `AGENTS.md` is the main repo contract.
- `.codex/` and `.agents/skills/` are the Codex-specific operating layer.
- `scripts/` contains canonical cross-platform commands.
- `cli/` remains a thin wrapper layer.
- `docs/graphs/generated/` is local-output only unless the project explicitly chooses another policy.
- `language_packs/` is optional and exists only when the repo uses the base-workspace-plus-overlay pattern.

## Update Rules
- Update this tree when directory ownership or command entrypoints change.
- Update `docs/source_overview.md` when package boundaries move.
- Update `docs/changelog.md` when template-wide policy changes.
