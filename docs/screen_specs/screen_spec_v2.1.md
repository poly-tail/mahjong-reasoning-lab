# 画面仕様書 v2.1

updated: `2026-05-10`

## 1. スコープ

- 現行画面仕様の正本
- 継承元: `old/screen_spec_v2.0.md`
- 詳細仕様は領域別文書へ分割して管理する

## 2. 正本文書

- 画面全体: [display_overview.md](./display_overview.md)
- 河表示: [river_display.md](./river_display.md)
- パネルとアラート: [alerts_and_panels.md](./alerts_and_panels.md)
- 操作系と Bridge: [controls_and_bridge.md](./controls_and_bridge.md)
- 見え枚数 UI: [visible_counts_ui.md](./visible_counts_ui.md)

## 3. 画面契約

- `AI TOP3` は `pt + 和了率` を表示する
- 1 位以外でも `top EV - 50pt` 以内は緑表示にする
- 相手パネルの `STATUS` は右詳細領域を `Player Status` に切り替え、Nodocchi 鳳凰卓4人打ち成績を表示する
- `STATUS` 成績ビューは `Nodocchiで開く` 外部リンクを常に持つ
- 河の記号は `L`, `Pl`, `P`
- `Visible x3/x4` は actual / inferred の統合グリッド
- inferred only の加算は青系の境界で区別する
- 推測見え枚数編集は「河クリック」と「37種牌セレクタ」の両方から入れる
- 自家の `2見え以下字牌` 一覧は自河よりやや下、自副露帯寄りに表示する
- `BG ... xN` は background worker の稼働数を示す

## 4. 互換メモ

- `rendered_display_guide.md` は旧導線
- `alert_flag_reference.md` は旧導線
- 新しい変更は旧ページではなく、上記の分割文書へ反映する
