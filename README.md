# Mahjong Reasoning Lab

## 試作UI（Focused Pruning Canvas）の起動

Windows PowerShellで次を実行します。

```powershell
cd "C:\Users\weath\Documents\プルーニングUI\focused-pruning-canvas"
npm start
```

ブラウザで **http://127.0.0.1:5174/** を開きます。起動中はPowerShellを開いたままにし、終了するときは `Ctrl+C` を押します。通常の起動で毎回 `npm install` は不要です。

**`Port 5174 is already in use` が出た場合**は、まず上記URLを開いてください。Focused Pruning Canvasが表示されれば起動済みなので、そのまま使えます。再起動する場合は、先に起動したターミナルで `Ctrl+C` を押してから `npm start` を実行します。

詳しい操作方法や初回セットアップは [試作アプリのREADME](focused-pruning-canvas/README.md) を参照してください。

## Project / Sheet 管理

Workspace は複数の Project を持ち、Project は複数の Sheet を持ちます。既存の nodes / edges / cases / rules / saved views はtop-level配列として維持し、Sheet 側に `node_ids` / `edge_ids` / `case_ids` / `rule_ids` / `saved_view_ids` を持たせて所属を管理します。

既存workspace v4を読み込む場合は、Default Project と Default Sheet を自動作成し、既存データをDefault Sheetへ所属させます。schema互換性を壊さず、IndexedDB保存とJSON export/importでも `projects`、`sheets`、`active_project_id`、`active_sheet_id`、`global_settings` を保持します。

新規Project / Sheet作成時には、初期テンプレートをチェックボックスで選択できます。テンプレートは `牌理`、`枚数`、`手役`、`抽象的な読み` の4種類です。デフォルトは全テンプレートONですが、Global SettingsでProject作成時・Sheet作成時の既定値を変更できます。空のProject / Sheetを作る場合はテンプレートを配置しません。

TemplateCatalog は Reading Probability Core の初期素材です。読み候補、初期ノード、influence edge、Reading Drawer候補、Exception Library候補、Residual Mass候補を作成しますが、押し引き判断、牌選択AI、EV計算、Action Recommendationは生成しません。同じSheetへのテンプレート適用はidempotentで、明示的な再適用時以外は重複配置しません。

画面上部のProject Selector / Sheet Selectorでactive Project / Sheetを切り替えられます。表示スコープは Sheet / Project / Workspace から選べます。Knowledge Mapは選択スコープに応じてノードとエッジを絞り込み、Case Workspaceはactive Sheetのcaseを優先し、新規caseやQuick Reading Inputで作成した要素をactive Sheetへ紐付けます。

Reading DrawerとException Libraryには Sheet / Project / Global のscope badgeを表示します。Residual Massにはactive Sheet / Project / Global / unknown bufferの送信先選択がありますが、現行では表示上の選択に留まり、追加要素の永続所属はactive Sheetです。Project / Globalへの実ルーティングは将来接続です。subgraph exportは選択中ノードだけでなく、active Sheet、active Project、Workspace全体を対象にできます。

Project / Sheet機能は、4軸の影響ウェイトを0〜100スコアとして扱う既存方針を維持します。候補確率と未配分確率だけを%表示し、影響ウェイトと軸確信度は確率ではありません。4軸の合計を100にする必要はありません。

麻雀の「読み」「候補確率」「未配分確率」「4軸影響」「例外候補」を、local-firstで整理するための知識マップGUIです。

Phase1の正式名称は **Reading Probability Core** です。完全自動推論器ではなく、読み候補・確率・影響ウェイト・軸確信度・未配分・例外集を構造化するMVPです。

Phase1は押し引き判断AI、牌選択AI、局収支EVエンジン、順位点EVエンジン、Action Recommendationではありません。4軸は読みの影響軸であり、押し引きや牌選択の最終判断軸ではありません。

## 既存アプリの実行方法

普段の起動はWindows PowerShellで次だけ実行します。

```powershell
cd "C:\Users\weath\Documents\プルーニングUI"
npm start
```

`npm install` は毎回不要です。初回、または依存関係が変わったときだけ実行します。
依存パッケージが見つからない場合は、`npm start` が標準出力に案内を出して停止します。

```powershell
npm install
npm start
```

起動後、Viteが表示するURLをブラウザで開きます。通常は次のどちらかです。

```text
http://localhost:5173/
http://127.0.0.1:5173/
```

本番ビルドの確認は次を実行します。

```powershell
npm run build
npm run preview
```

テストや静的チェックは次を使います。

```powershell
npm run test
npm run test:e2e
npm run lint
npm run format
```

Playwrightのブラウザが未インストールの場合は、先に次を実行します。

```powershell
npx playwright install chromium
```

要件定義書PDFを再生成する場合は次を実行します。

```powershell
node scripts/render-requirements-pdf.mjs
```

詳細仕様書PDFを再生成する場合は次を実行します。

```powershell
node scripts/render-specification-pdf.mjs
```

ユーザー向け仕様書PDFを再生成する場合は次を実行します。

```powershell
node scripts/render-user-specification-pdf.mjs
```

ユーザー目線の使い方ガイドPDFを再生成する場合は次を実行します。

```powershell
node scripts/render-user-guide-pdf.mjs
```

## コマンド一覧

```bash
npm start          # 開発サーバを起動
npm run dev        # 開発サーバを起動
npm run build      # TypeScriptチェック + production build
npm run preview    # build結果をローカルで確認
npm run lint       # ESLint
npm run test       # Vitestを1回実行
npm run test:watch # Vitestのwatchモード
npm run test:e2e   # Playwright E2E
npm run format     # Prettier check
```

## Stack

- React / TypeScript / Vite
- Tailwind CSS
- shadcn/ui方針のローカルUI primitives
- React Flow: 現行の公式パッケージである `@xyflow/react` を採用
- Zustand
- zod
- Dexie IndexedDB
- Vitest / React Testing Library / Playwright

`shadcn/ui` はCLI生成ではなく、MVPの依存を抑えるため `src/ui/components` に同系統の小さなフォーム/ボタン部品として実装しています。

## Folder Structure

テンプレートの `src/app` / `src/domain` / `src/infrastructure` / `src/ui` 境界をReactアプリ用に反映しました。

```text
src/
  app/              # AppShellとZustand store
  domain/           # zod schema、seed、export変換、分類、テンプレート、ラベル
  infrastructure/   # IndexedDB、file I/O
  shared/           # 小さな共通utility
  ui/               # 画面とUI primitives
docs/
  architecture.md
  schema.md
  future-integration.md
  concentration.md
  pruning-impact.md
  node-lock.md
  reading-utility.md
  requirements-definition.md
  detailed-specification.md
  specification.md
  quick-reading-input.md
  hand-value-range-theory.md
  residual-mass.md
  reading-drawer.md
  exception-library.md
  multi-step-reading.md
  educational-mode.md
tests/
  unit/
  e2e/
```

## Screens

トップ導線は作業目的で分けています。

- 局面で考える: Case WorkspaceとDecision Pipeline
- 理論を整理する: Mapping Inbox、Knowledge Map、Hand Value Range Lens、Rescue Rate Lens、Rule Builder Lite
- 確率と枝刈り: Probability Workbench、Influence Workbench、Pruning/Lock分析
- 読みを検証する: concentration、pruning、lock、ambiguity、chainを含むReasoning Lab
- 教材化する: teaching logと教育用説明
- データ管理: JSON import/export

### Mapping Inbox

- ChatGPTやnoteの麻雀考察を貼り付け、テンプレートから下書きノード案を作成
- テンプレート: 手牌価値レンジ、押し引き（読み整理）、危険牌比較、卓上動態/他家介入読み、ノードロック、枝刈り、読みの有用性、条件戦/順位点、中間状態
- 押し引き、危険牌比較、条件戦/順位点、安全度、卓上動態テンプレートは、Phase1では読み候補カテゴリ、context tag、observation candidate、exception candidateとして扱い、行動推奨は出さない
- 自然言語解析やLLM連携はせず、選んだテンプレートに沿って既存schemaの `type` / `tags` / `probability_role` / `pruning_hints` / `lock_mode` を埋める
- 作成ノードは通常のZustand commit、zod validation、undo historyに乗る

### Domain Lens / Theory Lenses

- Knowledge MapのDomain Lensで、全部、手牌価値、押し引き文脈、安全度、確率木、枝刈り、ロック、卓上動態、教育、反省のプリセット表示を切り替え
- Hand Value Range Lensで、進行度・聴牌率、打点、待ち・形の良さ、点数状況・行動閾値、mixed/unknown influence、追加観測候補を確認
- Rescue Rate Lensは卓上動態/他家介入読みとして、時間窓、脇介入イベント仮説、概算 `q_total = 1 - product(1 - q_i)`、上限警告を管理
- 旧称の脇救済率はPhase1では押し判断ではなく、卓上動態/他家介入読みとして扱う

正規4軸:

1. 進行度・聴牌率
2. 打点
3. 待ち・形の良さ
4. 点数状況・行動閾値

4軸は読みの影響先です。影響ウェイトは0〜100スコアであり、候補確率ではありません。4軸の合計を100にする必要はありません。同じ読みが複数軸を同時に強く動かしてよいです。軸確信度も0〜100スコアで、候補確率とは別です。

### Knowledge Map

- ノード/エッジの作成、接続、削除、複製
- 複数選択、グループ化、グループ折りたたみ
- 検索、タグフィルタ、ノード型フィルタ、保存ビュー
- 右Inspectorでノード属性、edge label/type、pruning hints、関連ruleを編集
- Ctrl+Z / Ctrl+Y とボタンでの元に戻す / やり直し
- Ctrl+Sまたは保存ボタンでの手動保存
- IndexedDBへの自動保存（デフォルト5分ごと、設定で変更可能）

### Case Workspace

- 局、供託、本場、巡目、点数、親/自家、リーチ、副露、捨て牌メモを入力
- 「読みを数値で反映」で、思いついた読みを4軸影響、候補確率、重み、枝刈り/ロック方針としてactive caseへ即反映
- choice groupの候補合計が100%未満なら未配分確率を表示し、具体候補、例外集、未知バッファ、計算用正規化、未配分保持から扱いを選ぶ
- 候補提案パネルで、副露意図、打点、進行度、待ち・形、危険牌、点数状況、卓上動態、相手傾向、例外/ノイズから追加候補を探す
- 例外集で、未配分から出た例外候補を保存し、active caseへの追加や次回候補化に使う
- 観測事象、仮説メモを管理
- 関連知識ノードをattach
- attachしたノードを「観測 → 仮説 → 条件 → 判断」列へ配置
- 「判断プロセス」表示で、洗い出し → 重み付け → 加算/合成 → 比較 → 選択 → 反省として同じattached nodesを派生表示
- 足りない要素パネルで、仮説/metric/choice group/判断メモ/反省メモ/mixed or unknown influenceなどを確認
- 未配分確率サマリで、active case内のchoice groupごとに合計、未配分、扱い、hard prune警告を確認
- 相反edgeがあるノードに相反バッジを表示
- Top-k仮説保持数、判断メモ、反省メモを保存

### Rule Builder Lite

- `Hard gate` / `Soft score` / `Override` / `Fallback` を分けたform editor
- target node idsをチェックボックスで管理
- rule JSONはworkspace JSON内に保持

### Probabilistic Propagation Layer

- Knowledge Graphとは別に、`probability_role !== none` のノードと `relation_layer: probabilistic` edgeだけを inference subgraph として扱う
- Choice Group Editorで排他的候補群を作成し、group内のposteriorを局所正規化
- Probability Inspectorで `prior` / `posterior` / `base_weight` / `dynamic_weight` / `lock_mode` / `distribution_family` を編集
- Lock UI: hard lock、soft lock、keep top-k、freeze ratio
- Propagation Preview: 更新前後のdiff、影響ノード、処理順、warningを表示し、確認後にApply
- Distribution-aware UI: categorical bar、interval range、bimodal/multimodal peak list、asymmetric tail、mixture weight editor
- Scenario Compare: A/B snapshotでロック前後、重み変更前後、分布仮定A/Bを比較

### Directional Influence Modeling

- `sign` はnodeではなく `source -> target metric` のinfluence edgeに持たせる
- `relation_layer: influence` を使い、semantic/probabilistic layerとは分離
- 同じsourceが複数metricへ異なる方向で作用できる
- 同じsourceとmetricでも `context_gate` が異なれば逆方向のedgeを併存できる
- Metric Lensで1つのmetricに対するsigned influenceを確認
- Ambiguity Panelで `mixed` / `unknown` / conflicting influences を分けて表示
- Branch Vector Summaryで枝ごとのmetric合成スコア、dominant direction、uncertainty、conflict countを表示
- Observation Plannerで曖昧性を減らす追加観測候補をgain/cost順に表示

### Reasoning Lab

- Graph View: semantic / probabilistic / influence / reasoning layerの分離を確認
- Metric Lens: metricごとのsigned influenceとBranch Vector Summaryを確認
- Concentration Lens: entropy、top_k_mass、peak_mass、hhiで確率質量の集中度を可視化
- Pruning Lab: hard prune / soft downweight / lock / keep-top-k / freeze-ratioのbefore-after diffを比較
- Lock Analysis: lock mode編集とaveraging safety estimatorを表示
- Ambiguity / Observation Planner: mixed / unknown / conflicting influencesを分け、observe/downweight/prune候補を表示
- Reading Chain Timeline: observation → hypothesis split → lock → prune → compare のような多段読みをreplay
- Educational Explanation Panel: reading utilityとteaching logから、なぜその読みが効く/効かないかを説明
- PruningとNode Lockの違いを説明カードで明示
- hard prune / soft downweight / keep top-k / hard lock / soft lock / freeze ratio / freeze concentration bandを操作グループで表示
- mixed/unknown influence、must_keep_top_k、薄く広い候補、固定中ノード、未配分確率が残るchoice groupに対する危険な枝刈りをwarning表示
- Reading Utilityで `residual_mass_before` / `residual_mass_after` / `residual_reduction` / `exception_candidates_added` / `unknown_buffer_remaining` を表示
- シミュレーション結果からテンプレートベースのteaching logを作成

### JSON I/O

- workspace全体を `mahjong-knowledge-map.workspace.v4` としてexport/import
- Knowledge Mapで選択したsubgraphを `pruning-ui.subgraph.v4` としてexport
- exportには selected nodes / edges / node metadata / related rules / pruning hints / weight placeholders に加え、`inference_subgraph`、`choice_groups`、`locks`、`weights`、`distributions`、`propagation_order`、`frozen_nodes`、`top_k_constraints` を含める
- v4 exportには `reasoning_lab` として concentration metrics、pruning actions、impact summaries、reading utilities、reading chains、averaging safety、teaching logs を含める
- 未配分確率はschema versionを上げず、既存の `exception` / `ambiguity_marker` ノード、tags、probability fields、pruning hintsで表現する

## Semantic Graph と Probabilistic Graph

このアプリは全グラフを確率伝播対象にしません。

- Semantic graph: 概念、メモ、根拠、注意書き、一般的な関係を表す。原則 `probability_role: none`
- Probabilistic inference layer: 仮説、状態、排他候補、シナリオ枝だけが `prior_probability` / `posterior_probability` を持つ
- Influence layer: 観測/仮説/枝がmetricへどの方向に作用するかをedgeとして表す
- Edgeも `relation_layer: semantic` と `relation_layer: probabilistic` を分ける
- Directional influenceでは `relation_layer: influence` を使う
- 伝播対象は inference subgraph に限定される

## Directionality

Directionality is edge-based, not node-based.

- `sign`: 方向。`+` / `-` / `mixed` / `unknown`
- `magnitude`: UI上の「影響ウェイト」。0〜100スコアとして表示し、内部は0〜1で保存
- `confidence`: UI上の「軸確信度」。0〜100スコアとして表示し、候補確率とは別に扱う
- `mixed`: 方向が文脈により割れている
- `unknown`: まだ評価不能

Ambiguityが大きい場合、pruningは警告または禁止されます。pruneできないが弱くできる場合はdownweight候補として扱います。追加観測でsign ambiguityを減らせる場合、`observation_candidate` がObservation Plannerに出ます。

確率を持つ代表ノード型:

- `hypothesis`
- `branch`
- `observation`
- `choice_group` は制御ノードとして `probability_role: control`
- `weight_modifier`
- `lock_controller`
- `probability_aggregate`

確率を持たない代表ノード型:

- `concept`
- `signal`
- `evidence`
- `question`
- 通常の `condition` / `metric` / `heuristic` / `scenario`

## Seed Data

初期データには以下のテーマを入れています。

- 読みの分布形状: 平均集中、区間拡散、二極化、多峰性、非対称テール
- 観測の癖: 選択バイアス、時系列ジャンプ、相関構造、類型混合
- 条件設計: State abstraction、Hard gate、Soft score、Override、Fallback、Top-k、Hysteresis、Event-driven update
- 対象テーマ: 押し引き文脈、染め読み、安全度評価、愚形固定仮説、相手手牌推定、打点レンジ推定
- inference seed: 染め本線 / 染め薄い / 染め否定、愚形固定 / 両面固定 / トイツ処理、高打点事故率、同色副露観測、選択バイアス注意modifier
- influence seed: 中盤の無筋手出し -> fold_risk(+)、現物増加 -> fold_risk(-)、手牌価値上昇 -> win_rate/value(+)、染め本線 -> safety(mixed)、手出し字牌連打 observation candidate
- reasoning lab seed: 上位質量集中、薄く広い枝集合、二極化枝集合、多峰性枝集合、狭い一点だけ削る読み、上位2枝に効く読み、ambiguityを減らす観測、marginが動かない観測、training case
- 判断ワークベンチseed: 中盤の染め副露読み、卓上動態読みを含む終盤読み整理、中間状態モデル、枝刈りとノードロックの違い

## Screenshots For README

READMEにスクリーンショットを貼る場合は、開発サーバを起動して以下を撮ると主要画面が揃います。

1. Mapping Inbox: 卓上動態/他家介入読みテンプレートで下書きノード案が見える状態
2. Knowledge Map: Domain Lens、凡例、マッピングガイド、右Inspectorが見える状態
3. Case Workspace: seed caseの4列思考経路と判断プロセスモードが見える状態
4. Hand Value Range Lens: 正規4軸（進行度・聴牌率、打点、待ち・形の良さ、点数状況・行動閾値）が見える状態
5. Rescue Rate Lens: 時間窓、イベント入力、上限警告が見える状態
6. Reasoning Lab: Pruning Labでbefore/after diff、Lock Analysis、Educational Explanationが見える状態
7. JSON I/O: workspace JSONとsubgraph export欄が見える状態

## Assumptions

- 完全な麻雀推論は実装せず、候補提示はtag/title/edge近傍による簡易スコアに限定
- groupは専用node typeではなく、`concept` nodeに `is_group` を持たせる
- Case dataには要件の最低項目に加え、UI入力例に合わせて `riichi_status`、`melds_summary`、`discard_notes` を追加
- React Flowの選択状態はReact Flow内部に任せ、アプリ側は選択IDだけ同期
- pruning-ui用のweightは実値ではなく `confidence` 由来のplaceholder
- Propagation Engineはchoice-group tree + DAG部分集合だけを扱い、一般循環確率グラフは解かない
- observation update、gate prune、weight modifier、lock、normalization、downstream、hysteresis/top-kの順に説明可能な更新を行う
- Reasoning Labのutility scoreは研究用の派生指標であり、勝敗結果や正解率ではない
- `compare` stepはMVP上のreading_chain表示用拡張で、probability actionではない

## Docs

- [docs index](./docs/README.md)
- [requirements-definition.md](./docs/requirements-definition.md)
- [requirements-definition.pdf](./docs/requirements-definition.pdf)
- [detailed-specification.md](./docs/detailed-specification.md)
- [detailed-specification.pdf](./docs/detailed-specification.pdf)
- [screen-specification.md](./docs/screen-specification.md)
- [specification.md](./docs/specification.md)
- [specification.pdf](./docs/specification.pdf)
- [user-guide.md](./docs/user-guide.md)
- [user-guide.pdf](./docs/user-guide.pdf)
- [architecture.md](./docs/architecture.md)
- [schema.md](./docs/schema.md)
- [future-integration.md](./docs/future-integration.md)
- [concentration.md](./docs/concentration.md)
- [pruning-impact.md](./docs/pruning-impact.md)
- [node-lock.md](./docs/node-lock.md)
- [reading-utility.md](./docs/reading-utility.md)
- [multi-step-reading.md](./docs/multi-step-reading.md)
- [educational-mode.md](./docs/educational-mode.md)
- [mahjong-mapping.md](./docs/mahjong-mapping.md)
- [decision-pipeline.md](./docs/decision-pipeline.md)
- [rescue-rate.md](./docs/rescue-rate.md)
- [pruning-vs-lock.md](./docs/pruning-vs-lock.md)

## 今回のMVPで出来ること

- 麻雀読みの知識ノードと関係edgeを地図として編集できる
- Mapping Inboxで考察メモから下書きノードを作れる
- 具体局面に知識ノードを貼り、観測/仮説/条件/判断に並べてレビューできる
- Case Workspaceで判断プロセスモードを使える
- Case Workspaceで読み数値入力から4軸influence edgeとchoice group候補を作成できる
- 手牌価値レンジ理論と卓上動態/他家介入読みを専用Lensで整理できる
- Hard gate / Soft score / Override / Fallbackを最低限のrule JSONとして保存できる
- workspace JSONとpruning-ui向けsubgraph JSONをexport/importできる
- 確率inference subgraphの正規化、lock、preview、scenario compareができる
- metricごとのdirectional influence、曖昧性、枝ベクトル、観測計画を確認できる
- concentration、pruning impact、node lock、reading utility、多段reading chain、educational explanationをReasoning Labで確認できる
- ブラウザローカルのIndexedDBに手動保存でき、デフォルト5分ごとの自動保存も設定できる

## 候補木ビュー

「確率と枝刈り」の既定表示として、読み候補を候補木ビューで確認できます。内部データは従来どおりグラフ/DAGのまま扱い、UI上だけを木構造風に投影します。schema v4、workspace v4、保存形式は変更しません。

候補木ビューでは、左ペインに候補グループ、候補枝、4軸影響、未展開の枝、例外の枝置き場を表示します。中央ペインでは選択した枝の候補確率、影響スコア、軸確信度、観測、例外、操作履歴を確認します。右ペインでは `枝を切る`、`枝を弱める`、`有力枝を残す`、`枝を固定する`、`比率を固定する` などの日本語ラベルで枝操作を選べます。

Project / Sheet / Workspace のスコープ切替に対応し、新規ProjectまたはSheet作成時の `牌理`、`枚数`、`手役`、`抽象的な読み` テンプレートは初期枝として確認できます。未展開の枝、未知の枝、例外の枝置き場が残る状態では、枝を切る前に反映前確認で警告を確認します。

現行の候補木ビューは読み候補の投影、操作種別の選択、警告プレビューまでを担当します。候補木内の `反映前確認` / `反映する` / `元に戻す` と、未展開・例外への送信ボタンは永続データを変更しません。実際の確率編集、伝播preview適用、枝刈り記録は `詳細編集` またはReasoning Labで行います。

## まだ出来ないこと

- 本格的な牌譜解析、リアルタイム対局連携、完全自動推論
- 高度な確率更新、視覚的な条件木エディタ、重み付きpruning UI本体
- ベイズネット完全実装、一般循環グラフの確率伝播、数式DSL
- 本格的なSankey描画、確率木専用の高度なビジュアルエディタ、utility式の学習
- クラウド同期、認証、複数人同時編集
- Tauri/Electron packaging

## pruning-ui との接続案

- `pruning-ui.subgraph.v4` を別プロジェクトのimport pointにする
- `pruning_hints` で Hard gate候補、score-only、override-only、Top-k保持を事前分類する
- `weight_placeholders` をpruning-ui側の重み編集初期値として使う
- `inference_subgraph`、`choice_groups`、`locks`、`weights`、`distributions`、`propagation_order` をpruning-ui側の確率木/重み編集初期状態にする
- `reasoning_lab` の concentration / impact / utility / chain / teaching log をpruning-ui側の説明可能な操作履歴として使う
- ruleの `target_node_ids` とselected subgraphのnode idを対応させ、条件木/確率木への変換を別レイヤーに分離する

## 本格推論エンジンへ拡張する時の論点

- 観測イベントの正規化と牌譜parserの境界
- Soft scoreの相関補正と二重計上防止
- 例外Overrideの優先順位と衝突解決
- Top-k保持の打ち切り条件
- confidence / reproducibility / source_typeを学習や検証データにどう接続するか

## 今回の追加実装で出来るようになったこと

- 確率質量の集中度を見て、どの枝を削ると分布が動きやすいかを確認できる
- prune / downweight / lock のbefore-after diffを保存し、delta_massやmetric-wise vector deltaを追える
- ノードロックと平均近似の安全度を `safe` / `caution` / `unsafe` で見られる
- reading utilityで、狭い一点だけ削る読みを過大評価しにくくした
- 多段読みchainをreplayし、stepごとの分布差分とrationaleを残せる
- 教育用seed caseとteaching logで、distribution shape / concentration / ambiguity / projection marginを説明できる

## 追加後もまだ未実装のこと

- 完全な麻雀AI推論、牌譜parser、対局リアルタイム連携
- 一般の循環確率グラフ、完全なベイズネット、連続分布の推定
- 本格Sankey/Waterfall描画、専用確率木エディタ、utility式の自動学習
- pruning-ui本体、Tauri/Electron packaging、クラウド同期

## 麻雀専用 / 汎用化できる部分

麻雀専用なのは seed data、metric名、局面フォーム、押し引き文脈/染め読み/安全度評価の語彙です。

汎用化できるのは Knowledge Graph / Probabilistic Inference Layer / Directional Influence Layer / Concentration Lens / Impact Simulator / Lock Analysis / Reading Chain / Educational Log の構造です。

## 次に本格実装すべき論点

- pruning-ui側で `pruning-ui.subgraph.v4` をimportし、同じimpact diffを再計算する
- observation eventの正規化と牌譜parserの境界を決める
- utility scoreの検証ログを蓄積し、選択バイアスを補正する
- mixed/unknown ambiguityの解消ワークフローを実戦レビューに接続する
- Reasoning Labのdiff履歴をケース単位で比較できるようにする

## 今後の課題: 観点横断補正時の未展開・例外確率

現行Phaseでは、牌理読み、枚数読み、手役読み、抽象的な読みを、それぞれ別の候補木・別の100%空間として扱います。各候補木の入力確率、未配分確率、例外集、4軸影響スコアを混ぜません。

将来的に観点横断の補正を行う場合、抽象的な読みが手役読みや牌理読みの候補分布を大きく変えることがあります。ただし、薄くなった候補の確率質量を常に他の既存候補へ全量再配分できるとは限りません。既存候補の説明力が低い、有力候補が少ない、mixed / unknown が残っている、部分的な牌姿パターン照合が不足している、抽象読みは濃いが対応する具体候補が未定義、といった場合は、未展開の枝、例外の枝置き場、未知バッファの確率を増やす必要がある可能性があります。

これは現時点では実装しません。Phase1では観点別候補木を分けて保持し、各候補木の100%空間を混ぜず、入力確率、未配分確率、例外集を保持するところに留めます。4軸影響スコアは候補確率ではなく、候補確率100%空間には混ぜません。抽象読みだけで既存候補を自動的に大きく切ることも行いません。

将来検討する場合は、入力確率、枚数補正後重み、横断補正後重み、計算用確率、未展開・例外確率を分離表示し、既存候補へ寄せるのか未展開・例外へ戻すのかをプレビューで区別します。横断補正ルールごとの信頼度、統合後分布への影響ログ、部分的な牌姿パターン照合による妥当性検証も必要です。
