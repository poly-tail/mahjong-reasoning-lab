# AGENTS.md

This repo is a local-first React app for mahjong knowledge mapping.

## Layout

- `src/app`: app shell, navigation, Zustand store
- `src/domain`: zod schemas, seed data, export transformation, labels
- `src/infrastructure`: Dexie persistence and browser file helpers
- `src/ui`: screens and small UI primitives
- `docs`: architecture, schema, future integration notes
- `tests/unit`: Vitest and React Testing Library
- `tests/e2e`: Playwright smoke tests

## Commands

- `npm run dev`
- `npm run build`
- `npm run lint`
- `npm run test`
- `npm run test:e2e`
- `npm run format`

## Constraints

- Keep the domain schema usable outside React.
- Validate persisted/imported/exported data with zod.
- Keep the app local-first; do not add auth, cloud sync, server DB, or multiplayer features.
- Do not turn Rule Builder Lite into a full condition-tree editor inside this MVP.
- Update README and docs when schema, commands, or folder ownership change.
