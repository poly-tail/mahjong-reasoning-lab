# Screen Spec v2.0

## 1. Positioning

- This version inherits `old/screen_spec_v1.9.md` and adds the 2026-04-11 follow-up for the full alert / flag / display-signal inventory.
- The canonical per-signal reference now lives at `docs/screen_specs/alert_flag_reference.md`.

## 2. Self-Hand Side

- `AI TOP3` keeps pystyle raw expected-value text.
- The compact `SELF` alert area to the right of `AI TOP3` remains mutually exclusive:
  - red `LOW EV`
  - yellow `EV<800`
  - green `HIGH EV`
- The visible-dora pill is always shown to the right of `SELF`.
- Visible-dora digits are full-width and include visible red dora in the count.
- Self-hand honor tiles show visible-count digits at the tile's top-right.

## 3. Opponent Player Panels

- `Remain` is shown as `current/no-temp` when both values exist.
- The `ALERT` section may show:
  - `Remain`
  - `門前`
  - `手役傾向`
  - `染/対々 UP`
  - `両面チー3-7`
  - `思考時間聴牌近`
  - `Push`
  - `Push解除`
- `Push` remains purple, `Push解除` remains green.
- `Push` / `Push解除` may persist for about three turns.

## 4. River Tile Signals

- River discard frames remain:
  - red frame for called discard
  - yellow frame for post-call tedashi
- River discard top-side marker cluster remains:
  - pink circle for `3-visible`
  - purple circle for `4-visible`
  - yellow circle for awaseuchi
  - blue circle for lag
- Peak-thinking marker remains a red diamond on the rotated position of the pre-rotation lower edge.
- River tiles may additionally carry:
  - riichi-stick marker
  - thinking-time color bands
  - full-tile tint priority `purple > brown > red`

## 5. Right Detail and Self-Hand Supplements

- In the right-side `Visible x3 / x4` lists, suited `3..7` tiles are additionally framed:
  - pink frame in `Visible x3`
  - purple frame in `Visible x4`
- Self-hand suited tiles may also carry `3-visible / 4-visible` circle markers.

## 6. Sound Behavior

- Self-side and opponent-panel alerts use short transition-only sound.
- `HIGH EV`, visible-dora pill states, `Push`, and `Push解除` stay silent.
- Repaint of the same active state must not retrigger sound.

## 7. Related Docs

- detail reference: `docs/screen_specs/alert_flag_reference.md`
- shared rules: `ui_principles.md` / `screen_map.md` / `invariants.md` / `change_request.md`
- logic references: `docs/mahjong/logic/mahjong_danger.md` / `docs/integrations/pystyle_simulator_protocol.md`
