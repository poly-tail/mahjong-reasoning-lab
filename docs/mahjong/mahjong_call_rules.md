# 鳴き可否ルール

この文書は、XML 牌譜で全員の手牌が分かったあとに `lagged = 1` を `3` または `5` へ確定させるための、最小限の鳴き可否ルールをまとめたものです。

## 目的

- live packet では `lagged = 1` は「ラグがあったが本ラグか偽ラグか未確定」を意味する
- `lagged = 6` は `550ms` 以下の short system delay として別扱いにする
- XML 牌譜入力後は、各打牌時点の全員手牌で鳴きが可能だったかを確認できる
- そのため `discard_fact` の `lagged = 1` を次のどちらかへ更新する
  - `3`: 鳴きは可能だったが実際には鳴かれなかった
  - `5`: 鳴きは不可能だったので偽ラグの可能性が高い

## 判定に使う鳴き

現行の偽ラグ判定では、次の 2 種類だけを使う。`4` は欠番で、現行実装では使わない。

- チー
- ポン

カンやロンは、この判定にはまだ使わない。

## ルール

### チー

- チーできるのは捨て牌の下家だけ
- 数牌だけが対象
- 手牌にその牌を含む連続 3 枚形が作れる 2 枚を持っている必要がある

例:

- `4p` が捨てられたとき、下家が `2p3p`、`3p5p`、`5p6p` のいずれかを持っていればチー可能
- 字牌はチー不可

### ポン

- ポンは捨て牌の相手が誰でも可能
- ただし打牌者本人は除く
- 手牌に同じ牌を 2 枚持っていればポン可能

## 偽ラグ判定への適用

- `lagged = 1` の打牌ごとに、その打牌時点の全員手牌を確認する
- `lagged = 6` は system delay 側として扱い、この偽ラグ判定には入れない
- ここでいう全員には自分も含む。たとえば自分が上家の打牌に対してチーまたはポン可能なら、その打牌は `lagged = 5` にしない
- 下家がチー可能、または打牌者以外の誰かがポン可能なら `lagged = 3`
- 誰もチーもポンもできないなら `lagged = 5`
- 実際に鳴かれた打牌は別扱いで `lagged = 2`

## 参考

- Riichi Wiki M.League rules: https://riichi.wiki/M.League_rules
- 麻雀ルール入門 ポンとチー: https://mjan.net/introduction/pon.html
## 2026-04-11 Meld Decode Addendum

- `src/capture/meld_decoder.py` is the implementation source for Tenhou `N`-tag shape and copy decoding.
- For `pon` and `kakan`, the exact called copy from `raw_m` must not also be consumed from self hand. `consumed_tile_ids` are built from the remaining two copies after excluding the called copy.
- `called_tile_id` is the discarded tile taken from the river. `consumed_tile_ids` are the two tile IDs removed from the caller's concealed hand, so kamicha/toimen/shimocha pon all reduce the correct tiles.
- When meld-decode semantics change, keep this file, `src/capture/meld_decoder.py`, and `tests/test_meld_decoder.py` aligned.

## 2026-04-11 Lag Marker Addendum

- River-side green lag markers now use a self-hand-only heuristic in addition to the existing multi-player same-tile lag rule.
- The heuristic checks only seat `0`'s concealed-hand snapshot at the discard timing.
- If that snapshot cannot legally chi or pon the lagged discard, the UI treats the marker as `pon-lag-likely` and draws the green marker.
- This is a display-side hint only. It does not rewrite `lagged` itself and does not replace the full XML-side `lagged = 3 / 5` refinement rule.
