# 検証記録

## 実行環境

2026-09-05（Asia/Tokyo）。Windows PowerShell、Node v22.19.0、npm 11.5.2。Chromiumは既存Playwrightキャッシュを使用。
対象ディレクトリ: `focused-pruning-canvas/`。親アプリは変更していない。

## 実行済み

| 実行                                                                                             | 結果 / 終了コード                                                                   |
| ------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| Node/npm、Git状態、AGENTS、依存のengines/peerDependencies確認                                    | 実施 / 0                                                                            |
| 参照リポジトリのREADMEとローカル参照HEADの対象コード確認                                         | 実施 / 0。reference-review.md参照                                                   |
| `npm install --offline --no-audit --no-fund`                                                     | 失敗 / 1。ENOTCACHED。キャッシュにregistry metadataなし                             |
| 通常install（環境のオフライン設定を維持）                                                        | 失敗 / 1。ENOTCACHED                                                                |
| 既存lockを基に `npm install --package-lock-only --offline --ignore-scripts --no-audit --no-fund` | 成功 / 0。試作の依存へ整理したlockfileを作成                                        |
| 初回Vitest（sandbox内）                                                                          | 失敗 / 1。ViteのWindows子プロセス spawn EPERM                                       |
| 標準の承認経路を経たVitest実行                                                                   | 成功 / 0。初回10件、次回17件、保存追加後23件                                        |
| Playwright初回4件                                                                                | 2成功 / 2失敗、終了1。非表示file inputの横はみ出しと初回描画前の比較を検出          |
| 修正後Playwright4件                                                                              | 成功 / 0                                                                            |
| 回復・競合・ブラウザ合成IMEを追加したPlaywright8件                                               | 成功 / 0                                                                            |
| check途中のcomponent test                                                                        | 1失敗 / 終了1。jsdomでisContentEditableがundefinedになる境界を修正                  |
| 最終 `npm run check`                                                                             | 成功 / 0。2026-09-05 17:31 JST。5 files / 34 tests成功、型・lint・整形・build成功   |
| 最終 `npm run test:e2e`                                                                          | 成功 / 0。2026-09-05 17:27 JST。Chromium 8 tests成功、console.error / pageerrorなし |

## 最終成果の補足

本番出力はJS 525.10kB（gzip 163.70kB）、CSS 33.56kB。Viteの500kB chunk警告は残るが終了コードは0。警告閾値を変更して隠していない。単一画面の試作として維持し、分割の必要性は将来の実測に基づいて判断する。

原文一致テストの追加時に、jsdom内のimport.meta.url経由のファイル参照と整形後のcode fenceの相違を検出して修正。またWindows PowerShellの標準入力ASCII変換で崩れた生成ドキュメントを依頼原文からUTF-8ファイル経由で再生成した。seed内の原文は保持され、最終の一致テストは成功。

## 自己レビューと修正

- golden seedの重みは仕様の値を維持。初期rawと配分、F5/F6による古い減点の不適用を固定テストで確認。
- unknownと観測機会なしを否定にせず、抑制も台帳に保持。hardはverified・信頼度1だけ確定。
- 説明順位をdomain/explanationsへ集約し、画面とMarkdownで同じscore単位の順位を使用。
- Markdownに大量のbacktickを含む履歴でも、JSONの改行エスケープと概要のエスケープで偽blockを防ぎ、容量を不要に増やさない。
- file inputの非表示幅を修正。1280pxのペイン切替を相互に排他的にした。
- 数値フォームの入力中ドラフトを文字列で保持し、空欄でNaNを表示しない。
- メモの構造編集後も同じ行へフォーカスを戻す。
- CSSを責務別に分け、巨大な業務集約ファイルを作らない。原文はcode block内へ保全。

## 画像

`test-results/canvas-1440x900.png` と `test-results/canvas-1280x800.png` を生成し目視確認した。横はみ出し修正後の両サイズを確認済み。最終修正後の画像を再生成し、両サイズを目視確認した。1280では明示的な全体表示で残余枝まで表示した。
幅変更後のviewportは自動で動かさず、明示的な「全体を表示」を使用する。

## 未検証・制約

- 実際のMicrosoft IME等の手入力: 未検証。C06の合成イベント試験とは区別。READMEの手動手順を実施する。
- Linux上での実行、独立ディレクトリでのネットワークを使った `npm ci`: 未検証。現在の環境では親の既存依存を使用。
- GitHub CI: 独立配置用設定あり、実行未確認。親リポジトリでは入れ子workflowは自動実行されない。
- localStorageの同時書込を完全には排他できない。実測確率校正、麻雀理論の妥当性、巨大Boardの性能保証は対象外。

失敗・未実行をpassとして記録しない。再実行はREADMEのコマンドを、このパッケージのディレクトリで行う。
