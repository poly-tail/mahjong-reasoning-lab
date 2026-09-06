## 17. 受入条件とテスト

acceptance.mdにID、要件、実装箇所、テスト、状態を対応づける。
仕様に適合させるための実装を行い、seedや期待値を結果に合わせて無断で書き換えない。

### A：ドメイン

A01：seedのrawScoreが第10節と一致、配分合計が許容誤差1e-10以内で1。
A02：大きい有限スコアでも安定化softmaxがNaN/Infinityを返さない。
A03：手動prune、復元、冪等downweight、residual単独100%。
A04：mustKeep/residualのprune/削除拒否、hard false保護枝は0だが表示対象。
A05：maxAbs、同値時の安定選択、mean、sum、異符号不正、抑制台帳。
A06：同根soft gateとeffectの重複抑制、informationalゲートは加算なし。
A07：AND/OR/NOTの全真偽組合せ、unknown、空集合/不正参照/深さ制限。
A08：verifiedでない条件からhard falseを確定しない。
A09：機会なしの観測不在、confidence=0、when=false/unknownは寄与0。
A10：F5/F6変更で安手非聴牌効果が適用外になり、H2が指定幅で上昇。
A11：台帳の合算とrawScore一致。再評価しても値が累積しない。
A12：自身変化/他候補変化/両方/除外変更の差分分類と対称分解の合計一致。
A13：候補追加削除・モデル設定変更は構造変更表示。偽の個別因果寄与なし。
A14：Note追加/階層変更/表示変更だけでスコア不変。

### B：編集・履歴・保存

B01：空Boardから仮説/Factor/Effect/Noteを作成し、自分の問いを保存できる。
B02：Noteの字下げ/字上げ、深さ/循環/異なるownerの防止。
B03：参照付き削除の確認、条件式参照のあるFactor削除拒否。
B04：一操作一履歴、no-op、Undo/Redo、Undo後編集、future切断、50件/2MiB上限と短縮通知。
B05：seedリセット/空BoardがUndo可能。選択/折り畳みは履歴なし。
B06：保存Envelopeが再帰せず、JSON/専用Markdownの全項目往復一致。
B07：invalid JSON、version不一致、重複ID、壊れた参照、原文/履歴の上限を拒否。
B08：import失敗/キャンセルで現行データ不変。成功置換確認。
B09：破損保存の保全、復旧、quota/security、保存失敗の未保存表示。
B10：StrictMode二重起動、再読込、Storage他タブrevision不一致を処理。

### C：UI・E2E

C01：起動時H1最大、H2/H5は低配分でも残り、未校正表示と凡例が見える。
C02：H2選択で薄まり上位理由/同根抑制/復活条件/原文が確認できる。
C03：F5=P → F6=P → 配分変化 → Timeline → Undo → Redo → reloadで復元。
C04：空Board作成 → 仮説追加 → 要因接続 → Note階層化 → export/importまでUI経由で完走。
C05：保護枝ボタンdisabledと理由表示、通常枝prune preview、復元。
C06：IME変換中のEnterで項目追加しない合成イベント試験と、実IMEの手動手順。
C07：フォーカス可視、名前付きフォーム、Tab退避、文字入力Undoとの共存。
C08：1440×900/1280×800でスクリーンショット。主要操作欠落/不要横スクロールなし。
C09：数値変更でノード位置/viewportが勝手に変わらない。
C10：console error、pageerror、未処理例外なし。

Unit/ComponentはVitest、React Testing Libraryを使う。
Canvas第三者ライブラリの内部実装をunitで再検証せず、ドメインと自作操作を対象とする。
実際のCanvasと保存動作はPlaywrightのChromiumで少なくともC01～C05を通す。
getByRole/getByLabel等のユーザー向け契約を優先し、sleep固定待ちでテストを通さない。
各テストでStorage/ID/時刻を分離し、テスト順序に依存させない。
失敗時のtrace/screenshotはgitignore対象の成果物ディレクトリへ残す。

## 実装・検証対応表

2026-09-05の最終checkとChromium E2Eで自動検証を確認。実行日時・失敗経緯・未検証環境は [verification.md](verification.md) が正本。

| ID  | 要件                                                                              | 実装箇所                                                                           | テスト                                                                                         | 状態                                          |
| --- | --------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- | --------------------------------------------- |
| A01 | seedのrawScoreが第10節と一致、配分合計が許容誤差1e-10以内で1。                    | `src/domain/{scoring,gates,explanations,deltas,validation,commands}.ts / src/seed` | tests/unit/scoring.test.ts・editing.test.ts・limits.test.ts                                    | 自動検証成功                                  |
| A02 | 大きい有限スコアでも安定化softmaxがNaN/Infinityを返さない。                       | `src/domain/{scoring,gates,explanations,deltas,validation,commands}.ts / src/seed` | tests/unit/scoring.test.ts・editing.test.ts・limits.test.ts                                    | 自動検証成功                                  |
| A03 | 手動prune、復元、冪等downweight、residual単独100%。                               | `src/domain/{scoring,gates,explanations,deltas,validation,commands}.ts / src/seed` | tests/unit/scoring.test.ts・editing.test.ts・limits.test.ts                                    | 自動検証成功                                  |
| A04 | mustKeep/residualのprune/削除拒否、hard false保護枝は0だが表示対象。              | `src/domain/{scoring,gates,explanations,deltas,validation,commands}.ts / src/seed` | tests/unit/scoring.test.ts・editing.test.ts・limits.test.ts                                    | 自動検証成功                                  |
| A05 | maxAbs、同値時の安定選択、mean、sum、異符号不正、抑制台帳。                       | `src/domain/{scoring,gates,explanations,deltas,validation,commands}.ts / src/seed` | tests/unit/scoring.test.ts・editing.test.ts・limits.test.ts                                    | 自動検証成功                                  |
| A06 | 同根soft gateとeffectの重複抑制、informationalゲートは加算なし。                  | `src/domain/{scoring,gates,explanations,deltas,validation,commands}.ts / src/seed` | tests/unit/scoring.test.ts・editing.test.ts・limits.test.ts                                    | 自動検証成功                                  |
| A07 | AND/OR/NOTの全真偽組合せ、unknown、空集合/不正参照/深さ制限。                     | `src/domain/{scoring,gates,explanations,deltas,validation,commands}.ts / src/seed` | tests/unit/scoring.test.ts・editing.test.ts・limits.test.ts                                    | 自動検証成功                                  |
| A08 | verifiedでない条件からhard falseを確定しない。                                    | `src/domain/{scoring,gates,explanations,deltas,validation,commands}.ts / src/seed` | tests/unit/scoring.test.ts・editing.test.ts・limits.test.ts                                    | 自動検証成功                                  |
| A09 | 機会なしの観測不在、confidence=0、when=false/unknownは寄与0。                     | `src/domain/{scoring,gates,explanations,deltas,validation,commands}.ts / src/seed` | tests/unit/scoring.test.ts・editing.test.ts・limits.test.ts                                    | 自動検証成功                                  |
| A10 | F5/F6変更で安手非聴牌効果が適用外になり、H2が指定幅で上昇。                       | `src/domain/{scoring,gates,explanations,deltas,validation,commands}.ts / src/seed` | tests/unit/scoring.test.ts・editing.test.ts・limits.test.ts                                    | 自動検証成功                                  |
| A11 | 台帳の合算とrawScore一致。再評価しても値が累積しない。                            | `src/domain/{scoring,gates,explanations,deltas,validation,commands}.ts / src/seed` | tests/unit/scoring.test.ts・editing.test.ts・limits.test.ts                                    | 自動検証成功                                  |
| A12 | 自身変化/他候補変化/両方/除外変更の差分分類と対称分解の合計一致。                 | `src/domain/{scoring,gates,explanations,deltas,validation,commands}.ts / src/seed` | tests/unit/scoring.test.ts・editing.test.ts・limits.test.ts                                    | 自動検証成功                                  |
| A13 | 候補追加削除・モデル設定変更は構造変更表示。偽の個別因果寄与なし。                | `src/domain/{scoring,gates,explanations,deltas,validation,commands}.ts / src/seed` | tests/unit/scoring.test.ts・editing.test.ts・limits.test.ts                                    | 自動検証成功                                  |
| A14 | Note追加/階層変更/表示変更だけでスコア不変。                                      | `src/domain/{scoring,gates,explanations,deltas,validation,commands}.ts / src/seed` | tests/unit/scoring.test.ts・editing.test.ts・limits.test.ts                                    | 自動検証成功                                  |
| B01 | 空Boardから仮説/Factor/Effect/Noteを作成し、自分の問いを保存できる。              | `src/domain/commands.ts / src/application / src/infrastructure`                    | tests/unit/editing.test.ts・persistence.test.ts・limits.test.ts                                | 自動検証成功                                  |
| B02 | Noteの字下げ/字上げ、深さ/循環/異なるownerの防止。                                | `src/domain/commands.ts / src/application / src/infrastructure`                    | tests/unit/editing.test.ts・persistence.test.ts・limits.test.ts                                | 自動検証成功                                  |
| B03 | 参照付き削除の確認、条件式参照のあるFactor削除拒否。                              | `src/domain/commands.ts / src/application / src/infrastructure`                    | tests/unit/editing.test.ts・persistence.test.ts・limits.test.ts                                | 自動検証成功                                  |
| B04 | 一操作一履歴、no-op、Undo/Redo、Undo後編集、future切断、50件/2MiB上限と短縮通知。 | `src/domain/commands.ts / src/application / src/infrastructure`                    | tests/unit/editing.test.ts・persistence.test.ts・limits.test.ts                                | 自動検証成功                                  |
| B05 | seedリセット/空BoardがUndo可能。選択/折り畳みは履歴なし。                         | `src/domain/commands.ts / src/application / src/infrastructure`                    | tests/unit/editing.test.ts・persistence.test.ts・limits.test.ts                                | 自動検証成功                                  |
| B06 | 保存Envelopeが再帰せず、JSON/専用Markdownの全項目往復一致。                       | `src/domain/commands.ts / src/application / src/infrastructure`                    | tests/unit/editing.test.ts・persistence.test.ts・limits.test.ts                                | 自動検証成功                                  |
| B07 | invalid JSON、version不一致、重複ID、壊れた参照、原文/履歴の上限を拒否。          | `src/domain/commands.ts / src/application / src/infrastructure`                    | tests/unit/editing.test.ts・persistence.test.ts・limits.test.ts                                | 自動検証成功                                  |
| B08 | import失敗/キャンセルで現行データ不変。成功置換確認。                             | `src/domain/commands.ts / src/application / src/infrastructure`                    | tests/unit/editing.test.ts・persistence.test.ts・limits.test.ts / tests/e2e/resilience.spec.ts | 自動検証成功                                  |
| B09 | 破損保存の保全、復旧、quota/security、保存失敗の未保存表示。                      | `src/domain/commands.ts / src/application / src/infrastructure`                    | tests/unit/editing.test.ts・persistence.test.ts・limits.test.ts / tests/e2e/resilience.spec.ts | 自動検証成功                                  |
| B10 | StrictMode二重起動、再読込、Storage他タブrevision不一致を処理。                   | `src/domain/commands.ts / src/application / src/infrastructure`                    | tests/unit/editing.test.ts・persistence.test.ts・limits.test.ts / tests/e2e/resilience.spec.ts | 自動検証成功                                  |
| C01 | 起動時H1最大、H2/H5は低配分でも残り、未校正表示と凡例が見える。                   | `src/features / src/app`                                                           | tests/e2e/canvas.spec.ts                                                                       | 自動検証成功                                  |
| C02 | H2選択で薄まり上位理由/同根抑制/復活条件/原文が確認できる。                       | `src/features / src/app`                                                           | tests/e2e/canvas.spec.ts                                                                       | 自動検証成功                                  |
| C03 | F5=P → F6=P → 配分変化 → Timeline → Undo → Redo → reloadで復元。                  | `src/features / src/app`                                                           | tests/e2e/canvas.spec.ts                                                                       | 自動検証成功                                  |
| C04 | 空Board作成 → 仮説追加 → 要因接続 → Note階層化 → export/importまでUI経由で完走。  | `src/features / src/app`                                                           | tests/e2e/canvas.spec.ts                                                                       | 自動検証成功                                  |
| C05 | 保護枝ボタンdisabledと理由表示、通常枝prune preview、復元。                       | `src/features / src/app`                                                           | tests/e2e/canvas.spec.ts                                                                       | 自動検証成功                                  |
| C06 | IME変換中のEnterで項目追加しない合成イベント試験と、実IMEの手動手順。             | `src/features / src/app`                                                           | tests/component/keyboard.test.tsx / tests/e2e/resilience.spec.ts                               | 合成イベント成功・手動手順あり（実IME未実行） |
| C07 | フォーカス可視、名前付きフォーム、Tab退避、文字入力Undoとの共存。                 | `src/features / src/app`                                                           | tests/component/keyboard.test.tsx / tests/e2e/resilience.spec.ts                               | 自動検証成功                                  |
| C08 | 1440×900/1280×800でスクリーンショット。主要操作欠落/不要横スクロールなし。        | `src/features / src/app`                                                           | tests/e2e/canvas.spec.ts                                                                       | 自動検証成功                                  |
| C09 | 数値変更でノード位置/viewportが勝手に変わらない。                                 | `src/features / src/app`                                                           | tests/e2e/canvas.spec.ts                                                                       | 自動検証成功                                  |
| C10 | console error、pageerror、未処理例外なし。                                        | `src/features / src/app`                                                           | tests/e2e/canvas.spec.ts / tests/e2e/resilience.spec.ts                                        | 自動検証成功                                  |
