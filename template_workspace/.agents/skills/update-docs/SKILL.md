# update-docs

Use this skill when a change affects repo structure, commands, ownership boundaries, or reusable guidance.

## Goals
- Keep `README.md` aligned with the template's actual quick start and commands.
- Keep `docs/context.md`, `docs/project_guide.md`, `docs/source_overview.md`, and `docs/folder_structure.md` consistent.
- Record reusable template changes in `docs/changelog.md`.

## Checklist
1. Identify whether the change affects repo layout, command entrypoints, or documentation governance.
2. Update `README.md` for user-facing setup or command changes.
3. Update `docs/context.md` if the documentation contract changed.
4. Update `docs/project_guide.md` when the template's intended workflow or extension strategy changed.
5. Update `docs/source_overview.md` and `docs/folder_structure.md` when ownership boundaries or directories changed.
6. Add or update a `docs/changelog.md` entry for reusable template guidance.

## Rules
- Prefer one canonical explanation per topic and link to it from other docs.
- Do not leave stale command examples behind after moving to a new script or wrapper.
