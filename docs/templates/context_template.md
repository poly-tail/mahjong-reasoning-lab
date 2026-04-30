# プロジェクト文脈テンプレート

## 概要
- プロジェクト名: `Project *** Helper`
- 目的: `***` の収集、`***` の可視化、`***` の保存を一体化する
- 主な技術: `Python 3.**`, `Tkinter`, `CSV`, `PowerShell`, `Mermaid`
- 想定ユーザー: `operator ***`, `analyst ***`, `developer ***`

## 正本ドキュメント
- 最新要件書: `docs/requirements/current.md`
- 最新仕様書: `docs/specs/current.md`
- 最新画面仕様書: `docs/screen_specs/current.md`
- プロジェクト概要: `docs/architecture/project_guide.md`
- ソースコード概要: `docs/architecture/source_overview.md`
- フォルダ構成: `docs/architecture/folder_structure.md`
- 関数 / モジュール graph: `docs/architecture/src_call_graph.md`
- 変更履歴: `docs/changelog.md`
- troubleshooting: `docs/operations/troubleshooting/`
- analysis 前提: `docs/analysis/`

## 文書版管理ルール
- `requirements/`, `specs/`, `screen_specs/` は `*_v***.md` を追加し、旧版を残す
- `current.md` は `pointer + summary` だけを書き、全文の正本にはしない
- 版上げ時は該当 `current.md` と `docs/changelog.md` を同時更新する
- 関数 / モジュールの主要フローが変わったら `docs/architecture/src_call_graph.md` と `docs/graphs/` を更新する
- 運用障害、既知不具合、復旧手順は `docs/operations/troubleshooting/` に残す
- 再利用できる分析前提は `docs/analysis/`、一回限りの結果は `analysis_output/` に分ける

## 作業原則
- 変更時に必ず追従更新する文書: `docs/architecture/source_overview.md`, `docs/architecture/project_guide.md`, `docs/changelog.md`
- 版上げが必要になる変更: `public schema`, `screen contract`, `operator workflow`
- 実装と docs を同時更新する範囲: `src/***`, `docs/specs/***`, `docs/screen_specs/***`
- graph 再生成が必要になる変更: `service -> repository` の呼び出し方向や責務分割変更

## 命名規則
- クラス名: `***State`, `***Config`, `***Response`
- 関数名: `load_***()`, `build_***()`, `render_***()`
- 定数名: `***_WIDTH`, `***_FILENAME`, `DEFAULT_***`
- ファイル名: `service_***.py`, `window_***.py`, `rule_***.py`

## 運用ルール
- Git ブランチ運用: `feature/***`, `fix/***`, `docs/***`
- コミットメッセージ方針: `CH-***`, `fix: ***`, `docs: ***`
- テスト方針: `unit -> integration -> manual UI check`
- レビュー観点: `regression`, `legacy compatibility`, `doc sync`

## AI / 自動化向け指示
- 優先するファイル: `src/***`, `docs/specs/***`, `docs/screen_specs/***`
- 更新時の注意: `legacy semantics`, `CSV migration`, `UI overlap rule`
- 文書の言語: `Japanese primary, code identifiers in English`
- テンプレート置き場: `docs/templates/`
- graph 再生成コマンド: `./cli/render_docs_graphs.ps1`
