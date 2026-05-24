# 性能ホットスポット

更新日: `2026-05-24`

## 現在の重点

UI の重さは主に次の層で見る。

1. `side_panels`
2. `discards`
3. visible / suji / push / same-jun の派生計算
4. background thread の多重起動
5. Bridge / NAGA / Nodocchi の外部問い合わせ

## `discards`

### 以前の問題

- 河を描き直すたびに最大 `4人 x 18枚` を全描画していた。
- `_discard_tile_image()` が赤/茶/紫/4見え/思考時間の組み合わせごとに色付き `PhotoImage` を作っていた。
- Canvas item を作った後に `find_all()` で差分取得し、後付け tag を付けていた。

### 現行対策

- `(seat, local_index)` ごとに表示シグネチャを持つ。
- シグネチャが変わった牌だけ `live_async_discards_<seat>_<index>` tag で削除して再描画する。
- 変わらない牌は描画しない。ただし click spec と lag marker reference spec は毎回復元する。
- `_discard_tile_image()` は通常牌画像だけ返す。
- tint と思考時間 band は Canvas overlay で描画する。
- discard item は作成時に `tags=` を渡す。

### slow log

`UI discards slow` は次を出す。

- `cache_before`
- `items_after`
- `active`
- `drawn`
- `skipped`
- `changed`
- `stale_deleted`
- phase breakdown

## `side_panels`

重くなりやすい処理:

- `SUMMARY` の line ranking
- safe hand ranking
- 危険ランク描画
- Nodocchi `STATUS`
- player memo / detail image

現行対策:

- side panel signature cache を持ち、変化がない場合は描画を再利用する。
- Nodocchi は background thread + canvas queue へ逃がす。
- font measure は canvas-local cache を使う。
- slow log で phase breakdown を出す。

## background thread

常時多重起動を避ける対象:

- live suji bundle
- live red tint
- inferred visible
- awaseuchi confirm
- pystyle fetch
- Nodocchi status fetch
- NAGA query / NAGA auto query
- alert audio

方針:

- 同一 key の in-flight を持つ。
- `1 in-flight + pending 1` で十分なものは coalescing する。
- UI refresh token を background 完了だけで増やし続けない。

## 調査手順

1. stdout / 診断ログで `UI redraw slow`, `UI side_panels slow`, `UI discards slow` を見る。
2. `phases=[...]` の上位を見る。
3. `discards` では `drawn` が多いか、`skipped` が効いているかを見る。
4. `side_panels` では signature cache が hit しているかを見る。
5. `BG ... xN` が増え続ける場合は worker in-flight 管理を疑う。

## 関連

- [../screen_specs/river_display.md](../screen_specs/river_display.md)
- [../screen_specs/alerts_and_panels.md](../screen_specs/alerts_and_panels.md)
- [../specs/current.md](../specs/current.md)
