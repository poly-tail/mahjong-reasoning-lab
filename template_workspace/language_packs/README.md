# language_packs

The base workspace stays intentionally generic.

Use `language_packs/` to stage stack-specific overlays after a project chooses its runtime.

## Goals
- Keep the copied base workspace small and reusable.
- Avoid forcing Python-, Node-, or UI-specific files onto projects that do not need them.
- Make stack adoption explicit instead of smuggling runtime assumptions into the base template.

## Suggested Workflow
1. Copy `template_workspace/` into a new repo.
2. Keep the base workspace as-is while documentation and structure are still being shaped.
3. Once the runtime is chosen, copy the relevant pack guidance into the repo root and adapt it.
