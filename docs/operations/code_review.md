# コードレビュー規則

この文書は、変更レビュー時の観点と分類を定義する。

## 優先度

- `P0 Critical`: データ破壊、秘密情報漏洩、起動不能、保存イベント欠落など即時対応が必要。
- `P1 High`: live capture停止、UI描画停止、DB不整合、重大なrace/deadlock。
- `P2 Medium`: 一部機能の回帰、性能劣化、診断不足、互換性リスク。
- `P3 Low`: 文書不足、軽微な可読性、局所的な保守性。

## 確度

- `Confirmed`: コード、テスト、ログ、再現手順で確認済み。
- `Strong inference`: 実行経路から高確度に推定できる。
- `Hypothesis`: 仮説。修正せず調査項目として残す。
- `Not reproduced`: 確認したが再現しない。
- `Deferred`: 重要だが今回の安全な変更範囲を超える。

## 観点

- correctness
- regression
- exception handling
- state consistency
- lock scope
- deadlock
- race condition
- queue/backpressure
- process lifecycle
- thread lifecycle
- UI thread blocking
- data compatibility
- security/privacy
- observability
- performance
- test quality
- documentation drift

## レビュー手順

1. 変更領域の正本文書と既存テストを確認する。
2. 仕様変更、バグ修正、性能改善、リファクタを分けて見る。
3. runtime data、秘密情報、ログ、生packet、pcap、CSV DBをdiffやZIPへ含めていないか確認する。
4. state lock、queue、worker、Tk threadの境界を確認する。
5. 保存イベントの欠落、順序後退、coalescing不可イベントの破棄がないか確認する。
6. UIでは [../screen_specs/invariants.md](../screen_specs/invariants.md) の不変条件を確認する。
7. findings は優先度と確度を付け、根拠となるファイル/行とテストを添える。

## 報告形式

- Findingsを先に書く。
- 各findingに `重大度`, `確度`, `根拠`, `影響`, `推奨修正`, `必要テスト` を付ける。
- 問題がない場合も、未実行テストと残存リスクを明記する。
