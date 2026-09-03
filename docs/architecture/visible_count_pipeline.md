# 見え枚数パイプライン

更新日: `2026-07-26`

## 3層

1. actual visible
2. inferred visible
3. merged display

## actual visible

担当: `src/visible_tiles.py`

入力:

- 自分の手牌
- 全員の捨て牌
- 全員の副露
- ドラ表示牌

含めないもの:

- lag 推定
- 合わせ打ち判定
- manual inferred visible

出力:

- `visible_counts_34_index`
- `three_visible_tiles`
- `four_visible_tiles`
- `four_visible_tile34_index_set`
- `blocked_sequence_tile34_index_set`

## inferred visible

担当: `src/ui/table_renderer.py`

用途:

- lag marker reference
- red tint neighbor
- manual count
- candidate seat toggle

actual visible を書き換えず、画面表示専用の補正として扱う。

## merged display

`actual + inferred` を `4.0` で clamp して UI に出す。

表示:

- `Visible x3`
- `Visible x4`
- 河の 3見え marker
- 河の 4見え tint
- 自家 `2見え以下字牌`

## 合わせ打ち

- 履歴正本は `LiveRiverStore` 由来の全席 `discard_map` とし、global discard順で見る。
- 他家の手出しだけを起点にし、その後5回以内の捨て牌増加で同じ34種牌が切られたslotへ表示用フラグを付ける。
- 途中にtarget seat自身の別打牌があっても窓内なら有効とする。
- 起点側のツモ切り、副露公開、ドラ表示は起点にせず、副露・ドラ表示は5打牌窓も消費しない。
- targetは手出し/ツモ切りを問わない。
- append cacheによる候補抽出と `awaseuchi confirm` workerを分け、actual visible / inferred visibleのownershipは書き換えない。

## 関連

- [../screen_specs/visible_counts_ui.md](../screen_specs/visible_counts_ui.md)
- [../screen_specs/river_display.md](../screen_specs/river_display.md)
- [../analysis/performance_hotspots.md](../analysis/performance_hotspots.md)
