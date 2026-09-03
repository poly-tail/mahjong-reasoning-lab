# ドキュメント索引

`docs/` は要件、仕様、画面仕様、運用、分析、外部連携を役割ごとに管理する。

## 現行正本

- [要件定義 現行版](./requirements/current.md)
- [仕様書 現行版](./specs/current.md)
- [画面仕様書 現行版](./screen_specs/current.md)
- [変更履歴](./changelog.md)

## 画面仕様

- [画面全体概要](./screen_specs/display_overview.md)
- [河表示仕様](./screen_specs/river_display.md)
- [パネルとアラート仕様](./screen_specs/alerts_and_panels.md)
- [操作系と Bridge](./screen_specs/controls_and_bridge.md)
- [見え枚数 UI](./screen_specs/visible_counts_ui.md)

## 分析

- [性能ホットスポット](./analysis/performance_hotspots.md)
- [DB グラフツール](./analysis/db_graph_tool.md)
- [プレイヤー別シャンテン思考時間分析](./analysis/player_shanten_thinking.md)

## 外部連携

- [Tenhou UI Bridge](./integrations/tenhou_ui_bridge.md)
- [Nodocchi STATUS](./integrations/nodocchi_status.md)
- [NAGA 段位ポイント分析](./integrations/naga_ptev_analyzer.md)
- [pystyle simulator protocol](./integrations/pystyle_simulator_protocol.md)

## アーキテクチャ / 参照

- [プロジェクトガイド](./architecture/project_guide.md)
- [ソース概要](./architecture/source_overview.md)
- [データ構造](./architecture/data_structures.md)
- [ADR](./architecture/adr/README.md)
- [CSV DB 設計](./reference/csv_db_design.md)
- [牌 ID リファレンス](./reference/tile_id_reference.md)

## 運用

- [通常起動チェックリスト](./operations/live_startup_checklist.md)
- [Live Capture トラブルシュート](./operations/troubleshooting/live_capture.md)
- [Live Rendering トラブルシュート](./operations/troubleshooting/live_rendering.md)
- [リポジトリ横断回帰チェックリスト](./operations/regression_checklist.md)
- [コードレビュー規則](./operations/code_review.md)

## 更新ルール

- 画面変更は `screen_specs/` と `changelog.md` を更新する。
- データ構造や DTO を変えたら `specs/` と `reference/` を更新する。
- 要件・仕様・画面仕様の版を上げたら、各 `current.md` を同じ版へ向ける。
- 性能調査や分析スクリプトを追加したら `analysis/` に入口を追加する。
- 設計判断を変更したら `architecture/adr/` を更新する。
