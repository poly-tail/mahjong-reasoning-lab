# scripts

Cross-platform helper scripts live here.

## Rules
- Prefer Python here over PowerShell-only automation when the script should run on Windows, macOS, Linux, and CI.
- `cli/` should stay thin. If logic grows, move it into `scripts/` and keep the CLI as a wrapper.
- Scripts should print actionable error messages and use non-zero exit codes on failure.

## Canonical Scripts
- `validate_workspace.py`: required-file checks, cache-artifact checks, generated-artifact policy checks.
- `render_docs_graphs.py`: Mermaid render entrypoint. `--dry-run` works without Node.
- `clean_python_cache.py`: removes `__pycache__/` and `*.pyc`.
