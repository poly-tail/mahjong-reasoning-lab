# プロジェクトガイドテンプレート

## 目的
- 何を作るか: `*** helper`, `*** dashboard`, `*** capture tool`
- 何を管理するか: `*** state`, `*** records`, `*** analysis result`

## 全体像
- 正本モデル: `GameState`, `RoundState`, `***Record`, `***Config`
- 主処理: `capture -> normalize -> analyze -> persist -> render`
- UI / 出力: `Tkinter canvas`, `CSV`, `JSON`, `analysis_output/***`
- 永続化: `csv_db/***_fact_YYYYMM.csv`, `player_profiles.csv`, `logs/***`

## 実行フロー
### 通常系
1. `cli/***_main.ps1` または `python -m ***` で起動する
2. `src/***/loader_***.py` が入力を読む
3. `src/***/service_***.py` が業務ロジックを実行する
4. `src/ui/***_renderer.py` または `csv_db/***` へ結果を反映する

### 補助系
1. `tests/fixtures/***` または `mock_data_***.py` を使う
2. `docs/analysis/***` と `analysis_output/***` で結果を検証する

## 主要データ構造
- `State`: `*** current snapshot`, `*** cache`, `*** ui state`
- `Event`: `captured packet`, `user action`, `sync trigger`
- `Record`: `***_fact row`, `***_context row`, `*** summary row`

## 保存モデル
- 主テーブル: `***_fact_YYYYMM.csv`
- 補助テーブル: `***_context_YYYYMM.csv`, `player_profiles.csv`
- key: `***_id`, `version`, `captured_at`
- legacy semantics: `*_after_discard` のように列名と意味が完全一致しないものを明記する

## 文書管理フロー
- 要件 / 仕様 / 画面仕様は versioned file と `current.md` の組で管理する
- 旧版ファイルは削除せず残し、`current.md` だけ最新へ向ける
- 重要変更は `docs/changelog.md` に addendum として残す
- 構成変更時は `docs/architecture/source_overview.md` と `docs/architecture/folder_structure.md` を更新する
- 関数 / モジュールの流れが変わったら `docs/architecture/src_call_graph.md` と `docs/graphs/` を更新する
- 運用障害や既知不具合は `docs/operations/troubleshooting/` に残す
- 再利用できる分析前提は `docs/analysis/` に残し、単発結果は `analysis_output/` に分ける

## テンプレート / 流用資産
- 管理ドキュメント template: `docs/templates/requirement_template.md`, `docs/templates/api_spec_template.md`
- workspace template: `template_workspace/src/***`, `template_workspace/docs/***`
- graph source / generated: `docs/graphs/src/graph_***.mmd`, `docs/graphs/generated/graph_***.svg`
- troubleshooting template: `docs/templates/troubleshooting_note_template.md`

## 更新ルール
- 版上げが必要な変更: `public schema`, `screen contract`, `operator workflow`
- 同時更新する文書: `requirements`, `specs`, `screen_specs`, `source_overview`, `changelog`
