# Tenhou Hojo Helper API / Implementation Spec v2.0

## 1. Positioning

- This version inherits `old/api_spec_v1.9.md` and adds the 2026-04-11 display-signal normalization / documentation refresh.
- Main target modules are `src/ui/table_renderer.py`, `src/logic/danger_suji.py`, `src/capture/fragment_parser.py`, and `docs/screen_specs/alert_flag_reference.md`.

## 2. Self-Side Display Signals

### 2.1 `SelfHandValueAlertState`

- The renderer state still distinguishes `kind = none | low_ev | warning_ev | high_ev`.
- Raw EV display and alert-only adjusted EV remain separate.
- Sound behavior remains transition-based, with `LOW EV` limited to once per round and `HIGH EV` muted.

### 2.2 Visible-Dora Pill

- `_visible_dora_tile_count()` aggregates visible normal dora and visible red dora.
- `_format_visible_dora_tile_count_label()` renders the count with full-width digits.
- `_self_hand_visible_dora_alert_colors()` and `_self_hand_visible_dora_alert_dot_color()` map the states:
  - `<= 0`: red
  - `= 1`: yellow
  - `= 2`: neutral
  - `>= 3`: green
- Visible-dora states are display-only and do not trigger alert sound.

## 3. Opponent Panel Alert Catalog

- `_build_player_alert_indicators()` is the renderer-side catalog for visible panel alerts.
- Current indicator keys and labels are:
  - `remain_yellow` / `remain_red`
  - `menzen_yellow` / `menzen_red`
  - `hand_pattern_yellow` / `hand_pattern_red`
  - `suit_bias` -> `染/対々 UP`
  - `ryanmen_chi_37` -> `両面チー3-7`
  - `tenpai_near` -> `思考時間聴牌近`
  - `push:<discard_index>` -> `Push ...`
  - `push_release:<discard_index>` -> `Push解除 ...`
- `Push` and `Push解除` remain persistence-based panel states and are muted in `_player_panel_alert_sound_priority()`.

## 4. River Marker / Tint Sources

- River frames come from discard metadata:
  - `called` -> red frame
  - post-call tedashi -> yellow frame
- River circles come from:
  - `VisibleTileSummary` -> `3-visible` / `4-visible`
  - discard `lagged` -> lag
  - `_same_jun_match_discard_indices_by_seat()` -> awaseuchi
- Peak-thinking red diamonds come from the per-seat maximum `thinking_time_ms` discard after excluding the first discard.
- Full-tile river tint priority remains `four-visible purple > blocked-sequence brown > red highlight`.
- Self-hand honor visible-count digits and right-detail `Visible x3/x4` borders are renderer-only projections of the same visible-count summary.

## 5. Ordering / Live-Rebuild Contract

- `fragment_parser.py` must preserve `round_discard_index` and `event_index` on tracker discard copies during both normal parse and snapshot rebuild.
- Renderer-side river markers may sort tracker discards by those fields during live redraw after `REINIT`.

## 6. Documentation / Test Sync

- `docs/screen_specs/alert_flag_reference.md` is the canonical user-facing signal inventory.
- `tests/test_self_hand_alert.py` fixes self-side alert and visible-dora behavior.
- `tests/test_player_panel_alerts.py` fixes panel-alert labels, thresholds, persistence, and sound policy.
- `tests/test_discard_borders.py` fixes river marker, tint, awaseuchi, and peak-thinking marker behavior.
