# Mahjong Reasoning Lab ドキュメント

更新日: 2026-07-26

現行実装の正本は次の順で参照します。

- [要件定義書](./requirements-definition.md): Phase1 の目的、スコープ、受け入れ条件
- [詳細仕様書](./detailed-specification.md): データモデル、処理境界、現行実装の契約
- [画面仕様書](./screen-specification.md): 共通フレーム、画面構成、操作状態、表示上の制約
- [ユーザー向け仕様書](./specification.md): 利用者から見える機能と非対応範囲
- [使い方ガイド](./user-guide.md): 日常操作と推奨ワークフロー
- [アーキテクチャ](./architecture.md): レイヤー責務、データフロー、永続化
- [スキーマ](./schema.md): `WorkspaceDocument` と export JSON のフィールド契約
- [将来連携](./future-integration.md): pruning-ui 連携と Phase2 以降の論点

個別テーマの仕様・理論文書:

- [麻雀マッピング](./mahjong-mapping.md)
- [判断パイプライン](./decision-pipeline.md)
- [Quick Reading Input](./quick-reading-input.md)
- [手牌価値レンジ4軸](./hand-value-range-theory.md)
- [卓上動態 / 他家介入読み](./rescue-rate.md)
- [未配分確率](./residual-mass.md)
- [読みの引き出し](./reading-drawer.md)
- [例外集](./exception-library.md)
- [枝刈りとロック](./pruning-vs-lock.md)
- [集中度](./concentration.md)
- [枝刈り影響](./pruning-impact.md)
- [ノードロック](./node-lock.md)
- [Reading Utility](./reading-utility.md)
- [多段読み](./multi-step-reading.md)
- [教育モード](./educational-mode.md)

## 同期ルール

- `src/domain/schema.ts` を変更したら `schema.md`、`detailed-specification.md`、要件への影響を確認する。
- `src/app/AppShell.tsx` または主要 `src/ui/` 画面を変更したら `screen-specification.md` とユーザー文書を確認する。
- Project / Sheet、import / export、永続化を変更したら `architecture.md` と `schema.md` を同時に更新する。
- 現行UIに操作ボタンがあっても、永続データを変更しないプレビューだけの機能は「実行可能」と記載しない。
- 要件定義、詳細仕様、ユーザー向け仕様、使い方ガイドを変更したら対応PDFを再生成する。
