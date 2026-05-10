# 画面仕様書 現行版

> 現行版ファイル: `screen_spec_v2.1.md`
> 共通ルール: `ui_principles.md` / `screen_map.md` / `invariants.md` / `change_request.md`

## 現行版

- 版: `v2.1`
- 更新日: `2026-05-10`
- 継承元: `old/screen_spec_v2.0.md`

## 現在の重点

- `AI TOP3`, `SELF`, 状況表、相手パネルの役割分担を固定する
- 相手パネルの `STATUS` は Nodocchi 成績ビューを右詳細領域に開く
- `STATUS` 成績ビューは loading / success / failed / not found と `Nodocchiで開く` を表示する
- 河記号は `L`, `Pl`, `P` の 3 種を使う
- `Visible x3/x4` は実見え枚数 + 推測見え枚数の統合グリッドとする
- 自家の `2見え以下字牌` 一覧は自副露帯寄りに表示する
- `BG ... xN` をバックグラウンドワーカーの稼働表示として使う

## 現行の個別画面文書

- 画面全体: [display_overview.md](./display_overview.md)
- 河表示: [river_display.md](./river_display.md)
- パネルとアラート: [alerts_and_panels.md](./alerts_and_panels.md)
- 操作系と Bridge: [controls_and_bridge.md](./controls_and_bridge.md)
- 見え枚数 UI: [visible_counts_ui.md](./visible_counts_ui.md)
- バージョン索引: [screen_spec_v2.1.md](./screen_spec_v2.1.md)

## 関連文書

- 要件定義 現行版: [../requirements/current.md](../requirements/current.md)
- 仕様書 現行版: [../specs/current.md](../specs/current.md)
- 見え枚数パイプライン: [../architecture/visible_count_pipeline.md](../architecture/visible_count_pipeline.md)
- データ構造: [../architecture/data_structures.md](../architecture/data_structures.md)
- pystyle 自動モード: [../integrations/pystyle_auto_mode.md](../integrations/pystyle_auto_mode.md)
- Nodocchi 成績連携: [../integrations/nodocchi_status.md](../integrations/nodocchi_status.md)
