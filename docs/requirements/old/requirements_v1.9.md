# Tenhou Hojo Helper Requirements v1.9

## 1. Positioning
- This version inherits `requirements_v1.8.md` and adds the 2026-04-10 follow-up for pystyle-driven self alerts, opponent-panel alert sounds, and dual `Remain` display.
- Main target modules are `src/ui/table_renderer.py`, `src/logic/danger_suji.py`, `src/app/main.py`, and `src/app/hand_recommendation_service.py`.

## 2. GUI Requirements
- `REQ-GUI-34`: A `SELF` alert area must be shown to the right of the `AI TOP3` button on the self-hand side.
- `REQ-GUI-35`: The self-hand alert must have three active states.
- `REQ-GUI-35a`: Red `LOW EV` is shown when the alert-only expected value is `< 600`.
- `REQ-GUI-35b`: Yellow `EV<800` is shown when raw pystyle expected value is `< 800` and red is not active.
- `REQ-GUI-35c`: Green `HIGH EV` is shown when raw pystyle expected value is `>= 3000` and red/yellow are not active.
- `REQ-GUI-36`: The visible `AI TOP3` panel must keep pystyle's raw expected-value text and must not apply the open-hand `0.8` correction to the displayed EV string.
- `REQ-GUI-37`: Opponent player panels must show `Remain` as `current/no-temp` when both the current denominator and the no-temporary-safe baseline are available.
- `REQ-GUI-38`: Self-hand alert sounds and opponent player-panel alert sounds must be short and transition-driven.
- `REQ-GUI-39`: Repeated redraw of the same active alert must not retrigger sound.

## 3. Data / State Requirements
- `REQ-DATA-31`: Self-hand alert state must preserve both `raw_top_expected_value` and `adjusted_top_expected_value`.
- `REQ-DATA-32`: Open-hand EV correction must depend on whether any current self meld is actually open; closed-only `ankan` must not trigger the `0.8` correction by itself.
- `REQ-DATA-33`: Opponent-panel summary payload must expose both `denominator_count` and `denominator_count_without_temporary_safe`.
- `REQ-DATA-34`: pystyle request timing must use `concealed tile count + effective meld tile count`, where each meld contributes `3` tiles to the pre-discard structure count.
- `REQ-DATA-35`: Current self melds must be forwarded to pystyle as `melds[]` request entries.

## 4. Operations / Documentation
- `REQ-OPS-11`: `requirements/current.md`, `specs/current.md`, and `screen_specs/current.md` must point to `v1.9`.
- `REQ-OPS-12`: `docs/changelog.md`, `docs/architecture/project_guide.md`, `docs/architecture/source_overview.md`, `docs/integrations/pystyle_simulator_protocol.md`, and `docs/mahjong/logic/mahjong_danger.md` must reflect the v1.9 alert/remain changes.

## 5. Maintenance Requirements
- `NFR-MAINT-12`: Raw EV display logic and alert-only adjusted EV logic must remain separate so the UI cannot drift between shown value and alert threshold semantics.
- `NFR-MAINT-13`: Alert sound triggering must be keyed by alert-state transition, not by repaint frequency.
- `NFR-MAINT-14`: `Remain` alert thresholds continue to follow the current denominator value even when the baseline `no-temp` denominator is shown alongside it.
