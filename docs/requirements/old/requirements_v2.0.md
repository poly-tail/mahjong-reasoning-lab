# Tenhou Hojo Helper Requirements v2.0

## 1. Positioning

- This version inherits `old/requirements_v1.9.md` and adds the 2026-04-11 display-signal documentation refresh.
- Main target modules are `src/ui/table_renderer.py`, `src/logic/danger_suji.py`, `src/capture/fragment_parser.py`, and the `docs/screen_specs/*.md` set.

## 2. GUI Requirements

- `REQ-GUI-40`: All user-visible alerts, flags, markers, pills, and supplemental visible-count numbers must be documented in one canonical screen-side reference file.
- `REQ-GUI-41`: The screen-side reference must cover at least `AI TOP3`, `SELF`, visible-dora pill, self-hand honor visible-count digits, opponent-panel alerts, river markers, river tint, and right-side `Visible x3 / x4` borders.
- `REQ-GUI-42`: Opponent-panel alert documentation must include `Remain`, `門前`, `手役傾向`, `染/対々 UP`, `両面チー3-7`, `思考時間聴牌近`, `Push`, and `Push解除`.
- `REQ-GUI-43`: River-display documentation must include called/post-call frames, `3-visible` / `4-visible` / lag / awaseuchi circles, peak-thinking diamond, riichi marker, thinking-time bands, and discard-tint priority.
- `REQ-GUI-44`: The visible-dora pill documentation must state that the count includes visible red dora and uses full-width digits.
- `REQ-GUI-45`: Sound documentation must distinguish sounding alerts from muted states such as `HIGH EV`, visible-dora pill, `Push`, and `Push解除`.

## 3. Data / State Requirements

- `REQ-DATA-36`: The canonical display reference must map every user-visible signal to an existing renderer-facing source such as `SelfHandValueAlertState`, `OpponentSujiPanelSummary`, push-alert payloads, `VisibleTileSummary`, or discard metadata.
- `REQ-DATA-37`: Live tracker discards must preserve ordering metadata needed by renderer-side display signals, including awaseuchi and peak-thinking markers.

## 4. Operations / Documentation

- `REQ-OPS-13`: `requirements/current.md`, `specs/current.md`, and `screen_specs/current.md` must point to `v2.0`.
- `REQ-OPS-14`: `docs/screen_specs/alert_flag_reference.md` must be referenced from the current screen spec and from at least one management document.
- `REQ-OPS-15`: `docs/changelog.md`, `docs/architecture/project_guide.md`, `docs/architecture/source_overview.md`, and `docs/architecture/folder_structure.md` must reflect the v2.0 display-document refresh.

## 5. Maintenance Requirements

- `NFR-MAINT-15`: User-facing display documentation should summarize trigger meaning at screen level, while detailed formulas stay in logic documents to avoid duplicated numeric drift.
- `NFR-MAINT-16`: When a visible alert or marker changes meaning, the versioned screen spec and the canonical display reference must be updated in the same change.
