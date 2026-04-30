# Source Overview Template

Explain what each top-level source package owns.

## Package Roles

| Path | Responsibility |
|---|---|
| `src/app/` | `use-case orchestration, entrypoints, CLI/UI/batch handoff` |
| `src/domain/` | `domain model and deterministic business rules` |
| `src/infrastructure/` | `persistence, adapters, external access` |
| `src/shared/` | `shared constants, helpers, exceptions` |
| `src/ui/` | `presentation, rendering, panels, windows` |

## Non-`src/` Support Areas
- `scripts/`: `repo maintenance commands`
- `cli/`: `thin wrappers`
- `tests/`: `validation and regression checks`
- `language_packs/`: `stack-specific overlays, if used`

## Best Practices
- Keep `src/app/` free from low-level infrastructure details when possible.
- Move repeatable maintenance logic into `scripts/`.
- Treat generated artifacts as disposable outputs.
- Keep stack-specific bootstrapping out of the base workspace until the project adopts it.

## Doc Sync Rules
- Update `docs/folder_structure.md` when package boundaries move.
- Update `docs/project_guide.md` when ownership changes.
- Update `docs/src_call_graph.md` and `docs/graphs/src/*.mmd` when graph meaning changes.
