# Generated Graphs

This directory is for locally generated SVG outputs from Mermaid sources.

## Policy
- The shipped template keeps only this README.
- SVGs are local artifacts and should not be committed to the base template.
- Source files live in `docs/graphs/src/*.mmd`.

## Canonical Commands
```bash
python scripts/render_docs_graphs.py --dry-run
python scripts/render_docs_graphs.py
```

Windows wrapper:

```powershell
./cli/render_docs_graphs.ps1
```
