# Source Overview

`src/` is reserved for project-side application code. The base workspace keeps only package boundaries and README placeholders there.

## Package Roles

| Path | Responsibility |
|---|---|
| `src/app/` | use-case orchestration, entrypoint coordination, CLI/UI/batch handoff |
| `src/domain/` | domain model, deterministic business rules, core policy |
| `src/infrastructure/` | persistence, adapters, external system access |
| `src/shared/` | shared constants, helpers, exceptions, common utilities |
| `src/ui/` | presentation, rendering, window or panel coordination |

## Non-`src/` Support Areas
- `scripts/`: repository maintenance commands
- `cli/`: thin wrappers around scripts or app entrypoints
- `tests/`: validation and regression checks
- `language_packs/`: stack-specific overlays kept outside the base workspace

## Best Practices
- Keep `src/app/` free from low-level infrastructure details when possible.
- Move repeatable maintenance logic into `scripts/`, not README-only shell snippets.
- Treat generated artifacts as disposable outputs and regenerate them from sources.
- Keep stack-specific bootstrapping outside the base workspace until a project adopts a language pack.

## Doc Sync Rules
- When package boundaries move, update `docs/folder_structure.md`.
- When ownership changes, update `docs/project_guide.md`.
- When graph meaning changes, update `docs/src_call_graph.md` and `docs/graphs/src/*.mmd`.
