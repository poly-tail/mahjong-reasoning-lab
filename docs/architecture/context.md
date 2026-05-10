# プロジェクト文脈

## 概要
- プロジェクト名: Tenhou Hojo Helper
- 目的: 天鳳の局面情報をリアルタイム表示し、危険度・待ち・補助情報を扱える運用基盤を維持する
- 主な技術: Python 3.x、`tkinter`、`Pillow`、CSV DB

## 正本ドキュメント
- 最新要件書: `docs/requirements/current.md`
- 最新仕様書: `docs/specs/current.md`
- 最新画面仕様書: `docs/screen_specs/current.md`
- docs 全体の入口: `docs/README.md`
- プロジェクト概要: `docs/architecture/project_guide.md`
- ソースコード概要: `docs/architecture/source_overview.md`
- フォルダ構成: `docs/architecture/folder_structure.md`
- 手牌分析仕様: `docs/mahjong/logic/hand_analysis.md`
- 変更履歴: `docs/changelog.md`

## 作業原則
- 実装と docs は同一ターンで整合を取る
- `current.md` を更新するときは対応する版ファイルも同時に更新する
- `src/` の責務、入出力、保存形式、画面構成が変わったら `project_guide.md` / `source_overview.md` / `folder_structure.md` / `changelog.md` を確認する
- `src/capture/` の契約が変わったら `docs/integrations/packet_capture.md` と `docs/specs/current.md` を同時に更新する
- 画面レイアウト変更時は `docs/screen_specs/current.md` と固定版を更新する
- DB schema 変更時は `docs/reference/csv_db_design.md` と changelog を更新する

## 文書分類ルール
- 麻雀そのもののルールや判断基準は `docs/mahjong/`
- 外部接続や transport の説明は `docs/integrations/`
- 変わりにくい参照表は `docs/reference/`
- 復旧や運用手順は `docs/operations/`
- repo 全体の構成説明は `docs/architecture/`

## 命名と記述方針
- 変数・関数名は `snake_case`
- クラス名は `PascalCase`
- 定数名は `UPPER_SNAKE_CASE`
- `docs/` 配下の管理文書は原則日本語で記述する
- UI 文言は必要時のみ英語を併記し、説明本文は日本語を優先する

## テンプレート資産
- 再利用用テンプレは `docs/templates/` に置く
- 他案件へそのままコピーするワークスペース雛形は `template_workspace/` に置く
- 新しい管理単位や文書種別を追加した場合は、この `context.md` と template 側の両方へ反映する

## Codex 向け追従ルール
- ファイル追加、削除、移動、改名、責務変更を検知したら docs 更新要否を確認する
- 特に `docs/architecture/folder_structure.md`、`docs/architecture/source_overview.md`、`docs/architecture/project_guide.md`、`docs/specs/current.md`、`docs/screen_specs/current.md` は毎回確認対象とする
- docs 更新が必要な変更では、実装だけで止めず関連文書まで完了させる
