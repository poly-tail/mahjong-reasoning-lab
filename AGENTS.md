# AGENTS.md

このリポジトリで作業する Codex / agent 向けの入口ルールです。詳細仕様をここへ重複させず、既存の正本文書へ必ず辿ってから変更してください。

## 作業開始時の必須確認

- [docs/architecture/context.md](docs/architecture/context.md)
- [docs/architecture/project_guide.md](docs/architecture/project_guide.md)
- [docs/changelog.md](docs/changelog.md) の対象領域に関係する直近履歴
- 変更領域に対応する仕様書
- 関連テスト
- 現在の Git 差分

既存ファイルの上書き、削除、移動、改名を行う前に、そのファイルの役割、参照元、正本性を確認してください。

## 領域別ルーティング

パケットキャプチャ、parser、state、DB を変更する場合:

- [docs/integrations/packet_capture.md](docs/integrations/packet_capture.md)
- [docs/operations/troubleshooting/live_capture.md](docs/operations/troubleshooting/live_capture.md)
- [docs/analysis/performance_hotspots.md](docs/analysis/performance_hotspots.md)
- [docs/reference/csv_db_design.md](docs/reference/csv_db_design.md)
- [docs/specs/current.md](docs/specs/current.md)

UI、描画、レイアウトを変更する場合:

- [docs/screen_specs/current.md](docs/screen_specs/current.md)
- [docs/screen_specs/invariants.md](docs/screen_specs/invariants.md)
- 対象コンポーネントに対応する画面仕様
- [docs/analysis/performance_hotspots.md](docs/analysis/performance_hotspots.md)

麻雀判断ロジックを変更する場合:

- [docs/mahjong/logic/](docs/mahjong/logic/) 内の該当正本
- [docs/specs/current.md](docs/specs/current.md)
- 関連する分析・テスト

運用、配布、レビュー、回帰確認を変更する場合:

- [docs/operations/regression_checklist.md](docs/operations/regression_checklist.md)
- [docs/operations/code_review.md](docs/operations/code_review.md)
- [docs/architecture/adr/](docs/architecture/adr/)

## 変更原則

- 既存仕様を新規要求として再解釈しない。
- 既存挙動を変える場合は、変更前挙動、変更後挙動、理由、互換性、回帰テストを明記する。
- 推測による広範囲修正を避ける。
- バグ修正は可能な限り再現テストを先に追加する。
- 振る舞いを変えないリファクタでも関連テストを実行する。
- 仕様変更、バグ修正、性能改善、リファクタを最終報告で区別する。
- 実装と docs を同じタスク内で同期する。
- 秘密情報、Cookie、token、TLS keylog、生 packet、個人情報、runtime data を repository、ZIP、ログ出力、テスト fixture へ含めない。

## 完了条件

- 対象テスト実行
- 全体テストまたは実行可能な最大範囲のテスト実行
- Python 構文確認
- 回帰チェックリスト確認
- 必要な変更履歴更新
- 設計判断を変えた場合の ADR 更新
- 最終 diff レビュー
- 未確認事項の明示
