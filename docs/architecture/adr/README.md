# ADR

このフォルダは、実装や運用の設計判断を Architecture Decision Record として記録する。

## 運用

- 確定した判断だけを `Accepted` にする。
- 証拠不足、実装未完了、追加検証が必要な判断は `Proposed` または `Deferred` にする。
- 仕様変更、互換性影響、runtime data、並行処理、DB保存、UI snapshot の責務境界を変える場合は ADR を追加または更新する。
- 変更履歴は [../../changelog.md](../../changelog.md) を正本とし、ADRは理由と境界を記録する。

## 一覧

- [0001 既存docsを正本として再利用する](0001-reuse-existing-docs-as-source-of-truth.md)
- [0002 source配布ZIPとruntime backupを分離する](0002-separate-source-package-and-runtime-backup.md)
- [0003 live capture pipelineの責務境界を維持する](0003-live-capture-pipeline-boundaries.md)
