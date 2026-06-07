# Mahjong Reasoning Lab 要件定義書

作成日: 2026-06-08

## 1. 目的

Mahjong Reasoning Lab は、麻雀の観測、読み候補、仮説候補、候補確率、未配分確率、例外候補、4軸影響を local-first で整理するための作業UIです。

本プロジェクトは完全自動推論器ではありません。Phase1 は Reading Probability Core として、読み候補空間を人間が見直せる形へ構造化することに閉じます。

## 2. 背景

実戦レビューでは、候補を早く消しすぎたり、思い出せない例外を既存候補へ押し込んだり、押し引き結論だけを残して途中の読みが失われることがあります。

Phase1 では、候補確率、未配分確率、例外集、読みの引き出し、4軸影響を分け、読みの過程を保存します。

## 3. Phase1スコープ: Reading Probability Core

Phase1 の正式名称は Reading Probability Core です。

扱うもの:

- 観測
- 読み候補
- 仮説候補
- choice group
- 候補確率
- `raw_probability`
- `normalized_probability`
- 未配分確率 / residual mass
- unknown buffer
- exception library / 例外集
- reading drawer / 読みの引き出し
- 4軸影響
- 影響ウェイト
- 軸確信度
- `mixed` / `unknown`
- `hard prune` / `downweight` / `keep top-k` / `lock`

`hard prune`、`downweight`、`keep top-k`、`lock` は、行動判断ではなく読み候補空間の整理操作として扱います。

## 4. Phase1非スコープ

Phase1 では次を扱いません。

- 押し引きの最終判断
- 牌選択の推奨
- 局収支計算
- 順位点期待値計算
- 放銃率・和了率・期待値を網羅した行動推奨
- 「この牌を切れ」「ここは押せ/引け」という Action Recommendation
- 脇救済率を根拠にした押し判断

4軸評価だけで「押す/引く/何を切る」を推奨してはいけません。

## 5. 用語定義

- 候補確率: choice group 内の候補に割り当てる確率。UIでは%で表示します。
- 未配分確率: 候補合計が100%未満のときの残差。候補漏れ、例外、観測ノイズ、未知バッファを表します。
- 影響ウェイト: その読みが正しい場合に、その軸をどれだけ動かすかを表す0〜100スコアです。確率ではありません。
- 軸確信度: その軸への影響方向・影響ウェイトの見積もりをどれだけ信頼するかを表す0〜100スコアです。
- Reading Drawer: 未配分確率や思い出し漏れから候補を追加するローカルcatalogです。
- Exception Library: まだ候補化しきれない例外やノイズを保存する場所です。
- 卓上動態 / 他家介入読み: 脇の和了、放銃、鳴き、安牌供給、流局接近など、他家介入で局面文脈が変わる読み候補です。

## 6. ユースケース

- 実戦後に、観測、読み候補、候補確率、未配分確率を保存する。
- 候補確率合計が100%未満のとき、未配分を隠さず、候補追加、例外集、未知バッファ、明示按分、未配分保持から選ぶ。
- 1つの読みが、進行度・聴牌率、打点、待ち・形の良さ、点数状況・行動閾値のどこに効くかを記録する。
- `mixed` / `unknown` が残る軸では hard prune を避け、downweight / keep top-k を検討する。
- 脇の和了、放銃、鳴き、安牌供給を押し判断ではなく、卓上動態 / 他家介入読みとして候補化する。

## 7. 機能要件

- Quick Reading Input で読みタイトル、読みタイプ、確信度、4軸影響、候補確率、未配分確率、枝刈り/ロック方針を入力できる。
- 影響ウェイトと軸確信度はUI入力では0〜100を受け取り、内部保存では0〜1に変換する。
- 候補確率と未配分確率だけを%表示する。
- 4軸の影響ウェイトは各軸独立で、4軸の合計を100にする必要はありません。
- 同じ読みが複数軸を同時に強く動かしてよい。
- Reading Drawer から読み候補を choice group に追加できる。
- Reading Drawer から例外候補を Exception Library へ送れる。
- 未配分確率を既存候補へ按分する場合は、ユーザーが明示的に選択する。
- Rescue Rate Lens は Phase1 では卓上動態 / 他家介入読みとして表示し、行動推奨に接続しない。

## 8. 非機能要件

- local-first で動作し、通常利用でサーバーDB、認証、クラウド同期を使わない。
- 永続化、import、export は zod schema で検証する。
- 既存 workspace v4 と schema 互換性を壊さない。
- 依存追加なしで既存の React / TypeScript / Vite / Tailwind 構成を使う。
- ドキュメントPDFはリポジトリ内スクリプトで再生成できる。

## 9. データ要件

- `raw_probability` は入力値を保持する。
- `normalized_probability` は明示的な比較用正規化に使う。
- `residual_mass` は候補漏れ、例外、観測ノイズ、未知バッファとして保存できる。
- `unknown_buffer` は既存候補へ自動按分しない。
- 影響ウェイトは内部 `magnitude: 0.0-1.0` として保存する。
- 軸確信度は内部 `confidence: 0.0-1.0` として保存する。
- 旧タグの `push_fold`、`rescue_rate`、`rank_ev` は互換性のため残せるが、Phase1の表示では行動推奨に見せない。

## 10. UI要件

- Phase1 が Reading Probability Core であることを README と docs に明記する。
- Quick Reading Input では影響ウェイトを `70/100` のように表示する。
- Quick Reading Input では軸確信度を `70/100` のように表示する。
- 候補確率と未配分確率は `70%` のように表示する。
- `卓上動態 / 他家介入読み` は押し引き判断ではなく、読み候補として説明する。
- Mapping Inbox の押し引き、危険牌比較、条件戦/順位点、安全度、卓上動態テンプレートは、読み候補カテゴリ、context tag、observation candidate、exception candidate、future phase / experimental として扱う。

## 11. 警告・ガード条件

- 影響ウェイトが高く軸確信度が低い場合、過大反映の警告を出す。
- `mixed` / `unknown` の軸が残る状態で `hard_prune` を選ぶ場合、downweight / keep top-k を促す。
- 未配分確率がある状態で `hard_prune` を選ぶ場合、警告を出す。
- 未配分確率を隠す自動正規化は禁止する。
- 卓上動態 / 他家介入読みを行動推奨として表示しない。

## 12. 受け入れ条件

- 4軸が読みの影響軸として維持されている。
- 4軸が排他的候補や候補確率として表示されていない。
- 押し引き、牌選択、局収支、順位点EVが Phase1 非スコープとして明記されている。
- 脇救済率が Phase1 では卓上動態 / 他家介入読みとして再定義されている。
- 未配分確率が残っても自動で既存候補へ按分されない。
- README、関連docs、PDF生成物の説明が矛盾していない。
- `npm run lint`、`npm run test`、`npm run build` が通る。

## 13. 将来拡張 / Phase2以降

Phase2以降で検討できるもの:

- 押し引き判断支援
- 牌選択支援
- 局収支EV
- 順位点EV
- 牌譜parser連携
- より厳密な確率モデル
- pruning-ui 本体との双方向連携

これらは Phase1 の Reading Probability Core とは別レイヤーとして設計します。

## Project / Sheet 管理要件

- Workspace は複数の Project を保持できる。
- Project は複数の Sheet を保持できる。
- Sheet は nodes / edges / cases / rules / saved views / Reading Drawer候補 / Exception Library候補 / Residual Mass候補の所属IDを持つ。
- 既存top-levelの nodes / edges / cases / rules / saved_views は維持し、zod schema互換性とworkspace v4互換性を壊さない。
- 既存workspaceを読み込む場合、Default Project と Default Sheet を作成し、既存データをDefault Sheetへ所属させる。
- `projects`、`sheets`、`active_project_id`、`active_sheet_id`、`global_settings` はIndexedDB保存、JSON export/import、workspace normalizeの対象にする。
- 新規Project / Sheet作成時に `牌理`、`枚数`、`手役`、`抽象的な読み` の初期テンプレートを選択できる。
- デフォルトでは全テンプレートをONにする。Global SettingsでProject作成時・Sheet作成時の既定ON/OFFを変更できる。
- 空のProject / Sheetとして作成する場合、テンプレートを配置しない。
- TemplateCatalogは Reading Probability Core の初期素材を作る。押し引き判断、牌選択AI、EV計算、Action Recommendationは作らない。
- 同じSheetへの同じテンプレート適用はidempotentに扱い、明示的な再適用時以外は重複配置しない。
- 表示スコープは Sheet / Project / Workspace を切り替えられる。
- Knowledge Mapは表示スコープに応じてノードとエッジを絞り込む。
- Case Workspaceはactive Sheetのcaseを優先表示し、新規caseとQuick Reading Inputで作成した要素をactive Sheetへ紐付ける。
- Reading DrawerとException Libraryは Sheet / Project / Global のscope badgeを表示する。
- Residual Massは未配分候補の送信先として active Sheet / Project / Global / unknown buffer を選べる。
- subgraph exportは選択中ノード、active Sheet、active Project、Workspace全体の対象を選べる。
- 影響ウェイトと軸確信度は0〜100スコアであり、候補確率や未配分確率ではない。候補確率と未配分確率だけを%表示する。
- 4軸の合計を100にする必要はありません。同じ読みが複数軸を同時に強く動かしてよい。
