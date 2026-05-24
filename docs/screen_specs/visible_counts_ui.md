# 見え枚数 UI

更新日: `2026-05-24`

## レイヤ

| レイヤ | 担当 | 意味 |
| --- | --- | --- |
| actual visible | `src/visible_tiles.py` | 実際に公開された牌 |
| inferred visible | `src/ui/table_renderer.py` | UI 上の推定追加枚数 |
| merged display | `src/ui/table_renderer.py` | actual + inferred を画面表示用に統合 |

## `Visible x3 / Visible x4`

- actual visible と inferred visible の合計を grid 表示する。
- actual のみか inferred 加算ありかを枠や表示状態で区別する。
- 4見えが上限。
- 3見えは河 marker としてピンク丸を出す。
- 4見えは河 tint として紫を優先する。

## inferred visible 編集

- 河クリックから対象牌を選べる。
- 37種牌 selector からも選べる。
- 手動補正は inferred visible だけを書き換え、actual visible には触れない。

## 自家 `2見え以下字牌`

- 対象は 0見え / 1見え / 2見えの字牌。
- 公開枚数は捨て牌、副露、ドラ表示牌から数える。
- 表示位置は自家右側、副露帯寄り。
- 目的は「残された字牌」と「自家副露状況」を近い位置で比較しやすくすること。

## 関連

- [river_display.md](./river_display.md)
- [alerts_and_panels.md](./alerts_and_panels.md)
- [../architecture/visible_count_pipeline.md](../architecture/visible_count_pipeline.md)
