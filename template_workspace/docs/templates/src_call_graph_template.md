# Source Call Graph Template

Describe the graph sources, render policy, and canonical commands.

## Canonical Sources
- `docs/graphs/src/graph_name_1.mmd`
- `docs/graphs/src/graph_name_2.mmd`

## Generated Outputs
- Generated SVGs live in `docs/graphs/generated/`.
- Decide whether generated SVGs are committed or local-only artifacts.
- State that policy explicitly here and in `.gitignore`.

## Canonical Commands
```bash
python scripts/render_docs_graphs.py --dry-run
python scripts/render_docs_graphs.py
```

Optional Windows convenience wrapper:

```powershell
./cli/render_docs_graphs.ps1
```

## Graph Policy
- `.mmd` files are the source of truth.
- `.svg` files are generated artifacts unless the repo states otherwise.
- Update `README.md`, `AGENTS.md`, and `docs/changelog.md` when command or policy changes.

## Update Rules
- Update the hierarchy graph when package boundaries move.
- Update the flow graph when the main workflow changes.
- Update `.gitignore` and `docs/graphs/generated/README.md` when artifact policy changes.
