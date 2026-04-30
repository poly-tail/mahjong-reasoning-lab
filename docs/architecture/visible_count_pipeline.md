# 見え枚数パイプライン

更新日: `2026-04-15`

見え枚数系の処理は、次の 3 層を分けて管理する。

1. 実見え枚数
2. 推測見え枚数
3. 合わせ打ち

## 1. 実見え枚数

担当: `src/visible_tiles.py`

### 入力

- 自分の手牌
- 全員の捨て牌
- 全員の晒し牌
- ドラ表示牌

### 含めないもの

- lag
- 合わせ打ち用の公開イベント
- manual 推測加算
- 推測見え枚数 UI 状態

### 出力

- `visible_counts_34_index`
- `three_visible_tiles`
- `four_visible_tiles`
- `four_visible_tile34_index_set`
- `blocked_sequence_tile34_index_set`

## 2. 推測見え枚数

担当: `src/ui/table_renderer.py`

### ワーカー

- canvas ごとに常駐ワーカー 1 本
- request ごとに thread を増やさない
- 実見え枚数を読み取り専用で参照する

### 入力

- 実見え枚数サマリ
- self river の lagged discard
- opponent rivers の red tint discard
- lag reference mode: `L / Pl / N`
- candidate seat toggle
- manual tile count `x0..x4`
- delete 状態

### 出力

- `VisibleTileInferenceSummary`
- inferred entry card list
- 実見え枚数 + 推測見え枚数の上限処理後サマリ

### 上限処理

- `actual + inferred` の合計は `4.0` 上限
- UI 上も `4見え` 扱いで止める
- `Visible x3 / x4` の段判定は clamp 後の値を四捨五入して整数で行う

### 自動推測ルール

- lag `Pl`: 対象牌に `+1.8` を候補 seat へ配分
- red tint neighbor:
  - 同スーツ `±1` -> `+0.9`
  - 同スーツ `±2` -> `+0.7`
- red tint neighbor は各プレイヤー seat ごとの補正として積み上げる

## 3. 合わせ打ち

担当: `src/ui/table_renderer.py`

### 入力

- public discard / meld reveal / dora reveal event stream

### 暫定候補

- 直近 `7` 公開イベントだけを見る
- hit がある時だけ provisional candidate にする

### 確定判定

- provisional hit がある時だけ queue
- background で full confirm
- 違えば marker を消す

### 分離ルール

- 実見え枚数を増やさない
- 推測見え枚数を増やさない
- 実見え枚数の ownership を書き換えない

## 4. 右詳細パネル

`Visible x3 / Visible x4` は、実見え枚数と推測見え枚数の和集合を 1 枚のグリッドにして表示する。

- base list: actual visible
- append: inferred でその段に入った牌
- sort: representative tile id
- blue border: inferred で追加された牌
- pink border: `Visible x3` の数牌 `3..7`
- purple border: `Visible x4` の数牌 `3..7`

## 5. ポップアップ編集

self hand 左の推測見え枚数 popup は、選択 tile 用の header card を必ず持つ。

- 捨て牌 click: その捨て牌の `34種`
- 牌パネル button: 37種 selector から選ぶ
- red five は表示 37種、count は 34種
- tile image click: `x0 -> x1 -> x2 -> x3 -> x4 -> x0`
- `削除`: selected tile または entry を消す
- candidate seat button:
  - single click で toggle
  - double click でその seat だけ残す

## 6. 文書 / テスト

### 文書

- `docs/screen_specs/river_display.md`
- `docs/screen_specs/visible_counts_ui.md`
- `docs/analysis/performance_hotspots.md`

### テスト

- `tests/test_inferred_visible_counts.py`
- `tests/test_live_snapshot_cache.py`
- `tests/test_discard_borders.py`
