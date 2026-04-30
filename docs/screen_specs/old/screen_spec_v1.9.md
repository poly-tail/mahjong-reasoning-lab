# Screen Spec v1.9

## 1. Positioning
- This version inherits `screen_spec_v1.8.md` and adds the 2026-04-10 follow-up for `SELF` EV alerts, opponent-panel alert sound, and dual `Remain` notation.

## 2. Self-Hand EV Alert
- A compact `SELF` alert area is displayed to the right of the `AI TOP3` button.
- Neutral state keeps the muted `SELF` label without an active alert.
- Active states are mutually exclusive and use dot + label color together.
- Red state shows `LOW EV`.
- Threshold: alert-only EV `< 600`
- Alert-only EV is `raw EV * 0.8` only when the current self hand contains at least one open meld.
- Yellow state shows `EV<800`.
- Threshold: raw pystyle EV `< 800` while red is inactive.
- Green state shows `HIGH EV`.
- Threshold: raw pystyle EV `>= 3000` while red/yellow are inactive.
- The `AI TOP3` popup itself continues to show pystyle's raw expected-value text and is not display-corrected by the open-hand factor.

## 3. Opponent Player Panels
- The `Remain` text now shows both counts when available.
- Format: `Remain: current/no-temp`
- `current` is the denominator after temporary-safe suppression.
- `no-temp` is the baseline denominator with temporary-safe suppression excluded.
- Existing `Remain` alert colors remain tied to the current denominator threshold.
- Yellow: `Remain < 8.0`
- Red: `Remain < 6.0`
- Existing purple `Push` alert remains based on the current latest-discard alert payload.

## 4. Alert Sound Behavior
- Self-hand alert and opponent-panel alert both use short notification sounds.
- Sounds fire only when an alert newly appears or when the alert kind upgrades/changes.
- Repainting the same active alert must stay silent.

## 5. Non-Effects
- `DETAIL`, `LAYOUT`, discard river, meld band, and `AI TOP3` popup layout rules from `v1.8` remain unchanged unless explicitly noted above.
