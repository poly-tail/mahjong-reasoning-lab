# cli

`cli/` is a thin wrapper layer.

## Rules
- Put reusable logic in `scripts/` or the project's `src/app/`.
- Keep wrappers focused on argument forwarding and exit-code propagation.
- Treat PowerShell-only commands as convenience wrappers, not as canonical cross-platform entrypoints.

## Current Wrapper
- `render_docs_graphs.ps1`: Windows convenience wrapper around `python scripts/render_docs_graphs.py`
