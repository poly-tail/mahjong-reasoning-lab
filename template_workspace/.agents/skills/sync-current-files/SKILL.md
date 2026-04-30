# sync-current-files

Use this skill when versioned requirements, specs, or screen specs change.

## Goals
- Keep every `current.md` file pointing at the newest versioned document.
- Keep version history tables aligned with the actual files that exist.
- Ensure `docs/changelog.md` mentions the update.

## Checklist
1. Update the new versioned file first.
2. Update the matching `current.md` pointer.
3. Update the version history table in the same `current.md`.
4. Update `docs/changelog.md`.
5. If the version change affects repo flow or structure, also run the `update-docs` skill.

## Rules
- Do not change `current.md` without creating or updating the referenced versioned file.
- Keep pointer files short; put full detail in the versioned document.
