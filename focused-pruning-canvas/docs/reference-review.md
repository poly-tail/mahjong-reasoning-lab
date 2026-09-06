# 参照レビュー

参照: https://github.com/poly-tail/mahjong-reasoning-lab 。公開 README をブラウザで取得し、同じ origin を持つ作業ツリーの追跡済みファイルを読み取り専用で確認した。
参照コミット: `f9c5afb696160364e528f6c72ff313c0d3719b20`（ローカル HEAD。remote 最新との一致は未確認）。

確認済み: README.md、AGENTS.md、package.json、src/domain/schema.ts、src/domain/probability.ts、src/domain/pruningSafety.ts、src/infrastructure/db.ts、src/app/store.ts の履歴・保存経路。
参照先の AGENTS は資料として扱い、今回の試作に自動適用しない。

継承: local-first、React 非依存のドメイン、Zod 境界検証、競合候補と残余・保護、データ往復。
採用しない: Project/Sheet、汎用 KnowledgeNode、posterior の入力再利用、単一 \_reason、下流乗算、top-k と数値 lock、seed の不足要素自動補充、別々の Undo/Redo 正本。今回の仕様に従い、純粋な weighted-score と flat snapshot/cursor、破損保全を新規実装する。
これは今回に採用する設計の記録であり、参照アプリ全体の品質評価ではない。
