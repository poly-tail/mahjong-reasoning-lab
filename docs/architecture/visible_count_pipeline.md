# 見え枚数パイプライン

更新日: `2026-05-24`

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
- 同順合わせ打ち判定
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

## 同順合わせ打ち

- public discard / meld reveal / dora reveal event stream だけを見る。
- private hand draw は見ない。
- provisional hit と confirm worker を分ける。
- actual visible / inferred visible の ownership は書き換えない。

## 関連

- [../screen_specs/visible_counts_ui.md](../screen_specs/visible_counts_ui.md)
- [../screen_specs/river_display.md](../screen_specs/river_display.md)
- [../analysis/performance_hotspots.md](../analysis/performance_hotspots.md)
