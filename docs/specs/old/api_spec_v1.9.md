# Tenhou Hojo Helper API / Implementation Spec v1.9

## 1. Positioning
- This version inherits `api_spec_v1.8.md` and adds the 2026-04-10 follow-up for open-hand pystyle requests, self-alert multi-state rendering, transition-only alert sound, and `Remain: current/no-temp`.
- Main target modules are `src/ui/table_renderer.py`, `src/logic/danger_suji.py`, `src/app/main.py`, `src/app/hand_recommendation_service.py`, and `docs/integrations/pystyle_simulator_protocol.md`.

## 2. Data Model / Derived State

### 2.1 `OpponentSujiPanelSummary`
- `denominator_count: float` remains the current unresolved weighted line count after temporary-safe suppression.
- `denominator_count_without_temporary_safe: float | None` is added as the baseline unresolved weighted line count computed with `include_temporary_safe=False`.

### 2.2 `SelfHandValueAlertState`
- The renderer state distinguishes `kind = none | low_ev | warning_ev | high_ev`.
- It preserves both `raw_top_expected_value` and `adjusted_top_expected_value`.
- `adjusted_top_expected_value` is derived only for alert judgment.

## 3. pystyle Request Semantics
- `src/app/main.py` converts current self melds into pystyle `melds[]` entries through `_build_pystyle_self_meld_requests()`.
- `src/app/hand_recommendation_service.py` treats `chi`, `pon`, `daiminkan`, `ankan`, and `kakan` as `3` effective tiles each for pre-discard sizing.
- The request-side total hand size is `len(concealed_hand_tiles_37) + effective_meld_tile_count`.
- Request execution remains gated on total effective size being exactly `14`.

## 4. Renderer Rules
- `_adjust_self_hand_alert_expected_value()` applies the `0.8` factor only when at least one current self meld is open.
- `_build_self_hand_value_alert_state()` evaluates states in this order:
- red `LOW EV`: adjusted EV `< 600`
- yellow `EV<800`: raw EV `< 800`
- green `HIGH EV`: raw EV `>= 3000`
- The visible `AI TOP3` list keeps raw pystyle EV text even when red-alert judgment uses adjusted EV.
- `_format_player_panel_remain_text()` renders `Remain: current/no-temp` when the baseline field exists.

## 5. Alert Sound Gating
- `_should_play_self_hand_value_alert_sound()` returns true only when the current alert kind is active and differs from the previous kind.
- Player-panel alert sound gating compares stable alert keys by seat and only fires when a new key appears for that seat.
- Redraw of the same active state must not retrigger sound.

## 6. Related Tests
- `tests/test_self_hand_alert.py` fixes the threshold semantics for red/yellow/green self alerts and sound transitions.
- `tests/test_player_panel_alerts.py` fixes `Remain: current/no-temp` formatting and stable-key behavior for player-panel alerts.
