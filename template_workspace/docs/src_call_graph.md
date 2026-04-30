# Source Call Graph

This document defines the canonical sources and render flow for repository graphs.

## Canonical Sources
- `docs/graphs/src/project_hierarchy.mmd`
- `docs/graphs/src/project_flow.mmd`

## Generated Outputs
- Generated SVGs live in `docs/graphs/generated/`.
- The shipped template keeps only `docs/graphs/generated/README.md`.
- Recreate SVGs locally when needed instead of committing them to the base template.

## Canonical Commands
```bash
python scripts/render_docs_graphs.py --dry-run
python scripts/render_docs_graphs.py
```

Windows convenience wrapper:

```powershell
./cli/render_docs_graphs.ps1
```

## Graph Policy
- `.mmd` files are the source of truth.
- `.svg` files are disposable build artifacts.
- If graph commands or policy change, update `README.md`, `AGENTS.md`, and `docs/changelog.md`.

## Update Rules
- Update `project_hierarchy.mmd` when package boundaries move.
- Update `project_flow.mmd` when the repo's main workflow changes.
- Update `docs/graphs/generated/README.md` and `.gitignore` if local-output policy changes.
