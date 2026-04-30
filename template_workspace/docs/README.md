# docs

`docs/` is the canonical place for reusable project documentation.

## Canonical Files
- `context.md`: documentation contract and maintenance rules.
- `project_guide.md`: project purpose, scope, extension model, and Codex-facing workflow.
- `source_overview.md`: ownership boundaries for `src/`.
- `folder_structure.md`: repository tree and directory intent.
- `src_call_graph.md`: graph policy and graph update flow.
- `changelog.md`: reusable template updates and migration notes.
- `requirements/current.md`, `specs/current.md`, `screen_specs/current.md`: current pointers to versioned docs.

## Supporting Areas
- `analysis/`: reusable analysis notes and filters.
- `troubleshooting/`: operational recovery notes.
- `graphs/src/`: Mermaid sources.
- `graphs/generated/`: locally generated SVG outputs.
- `templates/`: document skeletons for new projects.

## Rules
- Prefer one canonical explanation per topic.
- Update `current.md` pointer files together with their versioned docs.
- Keep generated SVGs out of the template; regenerate them locally when needed.
