# ドキュメント索引

`docs/` では、要件、仕様、画面仕様、運用、グラフ、分析メモを役割ごとに分けて管理します。

## 現行文書

- [要件定義 現行版](./requirements/current.md)
- [仕様書 現行版](./specs/current.md)
- [画面仕様書 現行版](./screen_specs/current.md)
- [更新履歴](./changelog.md)

## 主要文書

- [プロジェクトガイド](./architecture/project_guide.md)
- [ソース概要](./architecture/source_overview.md)
- [データ構造](./architecture/data_structures.md)
- [見え枚数パイプライン](./architecture/visible_count_pipeline.md)
- [src コールグラフ](./architecture/src_call_graph.md)
- [Tenhou UI Bridge](./integrations/tenhou_ui_bridge.md)
- [通常起動チェックリスト](./operations/live_startup_checklist.md)
- [他環境セットアップ](./operations/other_environment_setup.md)
- [画面全体概要](./screen_specs/display_overview.md)
- [河表示仕様](./screen_specs/river_display.md)
- [パネルとアラート](./screen_specs/alerts_and_panels.md)
- [操作系と Bridge](./screen_specs/controls_and_bridge.md)
- [見え枚数 UI](./screen_specs/visible_counts_ui.md)

## 更新ルール

- 画面表示を変えたら `screen_specs/` と `changelog.md` を更新する
- データ契約を変えたら `requirements/` と `specs/` を同期する
- 呼び出し関係や階層図を変えたら `graphs/src/*.mmd` と生成 SVG を更新する

## グラフ再生成

```powershell
python scripts/render_docs_graphs.py
```
