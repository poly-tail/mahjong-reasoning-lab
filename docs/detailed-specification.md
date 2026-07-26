# Mahjong Reasoning Lab 詳細仕様書

作成日: 2026-06-08
更新日: 2026-07-26

## 1. 全体アーキテクチャ

Mahjong Reasoning Lab は React / TypeScript / Vite で実装する local-first アプリです。状態管理は Zustand、永続化は Dexie IndexedDB、データ検証は zod schema を使います。

Phase1 の正式名称は Reading Probability Core です。Phase1 は、観測、読み候補、候補確率、未配分確率、例外候補、4軸影響を整理する層であり、押し引き判断AIや牌選択AIではありません。

主な境界:

- `src/app`: app shell、navigation、Zustand store
- `src/domain`: zod schema、seed、taxonomy、Project / Sheet scope、template catalog、reading numerics、residual mass、export変換
- `src/infrastructure`: IndexedDB、file helpers
- `src/ui`: Case Workspace、Quick Reading Input、Workbench、Lens UI
- `docs`: 要件、詳細仕様、画面仕様、ユーザー仕様、理論、将来連携

## 2. データモデル

中心データは `WorkspaceDocument` です。workspace v4 互換を維持し、既存フィールドで Reading Probability Core を表現します。

主な要素:

- `KnowledgeNode`: 観測、仮説、metric、choice group、例外、曖昧性など
- `KnowledgeEdge`: semantic / probabilistic / influence の関係
- `CaseData`: active case と attached nodes
- `Project`: 研究テーマや用途の単位と所属Sheet ID
- `Sheet`: Project内の作業面と、node / edge / case / rule / saved view等の所属ID
- `GlobalSettings`: Project / Sheet作成時の既定テンプレートと空作成の既定値
- `ReadingImpactDraft`: Quick Reading Input の入力状態
- `ResidualMassSummary`: choice group の未配分確率と扱い
- `ReadingDrawerItem`: 未配分や思い出し漏れから候補化できるcatalog item

`WorkspaceDocument` はtop-levelの `nodes` / `edges` / `cases` / `rules` / `saved_views` を維持し、`projects` / `sheets` / `active_project_id` / `active_sheet_id` / `global_settings` を同じworkspace v4へ追加しています。未配分や例外は既存の node type、tags、probability fields、pruning hints を組み合わせて保存します。

表示スコープ `sheet` / `project` / `workspace` は `WorkspaceScopeMode` として定義しますが、`scopeMode` はZustandの一時UI状態であり、`WorkspaceDocument` へ永続化しません。

Reasoning Labの多段処理は `ReadingChain` / `ReadingChainStep` として保存し、`KnowledgeEdge.relation_layer` に `reasoning` を追加しません。

## 3. Semantic / Probabilistic / Influence layer

Semantic layer は説明、根拠、注意書きを扱います。原則として確率伝播対象ではありません。

Probabilistic layer は choice group、branch、hypothesis、probability aggregate などの候補確率を扱います。

Influence layer は、読みがmetricや4軸にどの方向で効くかをedgeとして扱います。`sign` は `+`、`-`、`mixed`、`unknown` を持ち、`magnitude` はUI上の影響ウェイト、`confidence` はUI上の軸確信度です。

影響ウェイトと軸確信度は候補確率ではありません。

## 4. Case Workspace

Case Workspace は1つの局面に、観測、仮説、条件、判断メモ、反省メモ、関連ノードを紐づけます。

Quick Reading Input で作成した読みノード、4軸 influence edge、choice group、未配分ノード、例外候補は active case に attach できます。

Case Workspace の表示はレビュー用です。Phase1では「この牌を切れ」「押せ/引け」を出しません。

## 5. Quick Reading Input

Quick Reading Input は、読みを数値で active case へ反映するUIです。

入力:

- 読みタイトル
- 読みメモ
- 読みタイプ
- 読み全体の確信度
- 4軸影響
- choice group 候補確率
- residual mass policy
- pruning / lock 方針
- context gate

4軸影響の入力:

- Direction: `+` / `-` / `mixed` / `unknown`
- Impact weight: slider 0〜100、number 0〜100、表示 `70/100`
- Axis confidence: slider 0〜100、number 0〜100、表示 `70/100`

内部保存:

- `magnitude = impactWeight / 100`
- `confidence = axisConfidence / 100`

候補確率と未配分確率は%で扱います。影響ウェイトと軸確信度は%ではなく、0〜100のスコアです。

## 6. Hand Value Range 4軸

正規4軸:

1. 進行度・聴牌率
2. 打点
3. 待ち・形の良さ
4. 点数状況・行動閾値

4軸は読みの影響射影先です。最終的な押し引き判断軸や牌選択軸ではありません。

仕様:

- 4軸は排他的候補ではない。
- 4軸は候補確率ではない。
- 4軸の合計を100にしない。
- 各軸は0〜100スコアで表示する。
- 内部保存は0〜1。
- 軸確信度も0〜100スコアで表示する。
- 1つの読みが複数軸を同時に強く動かしてよい。
- 影響配分を出す場合は派生表示であり、入力値ではない。
- 4軸は Action Recommendation ではない。

例:

「親リーチ後の無筋456」は、進行度・聴牌率に強く効く可能性があり、待ち・形の良さにも効きます。打点への影響は状況次第です。点数状況・行動閾値には「自分の文脈上、危険読みをどう重く扱うか」という読みの射影として効きます。

ただし、この4軸評価だけで「押す/引く/何を切る」を推奨してはいけません。

## 7. Residual Mass

Residual Mass は choice group の候補確率合計が100%未満のときの未配分確率です。

扱う値:

- `raw_probability`: 入力された候補確率
- `normalized_probability`: 明示的に比較するための正規化値
- `residual_mass`: 100%から候補合計を引いた残差
- `unknown_buffer`: まだ候補化しない未知部分
- `exception candidate`: 例外集へ送る候補
- `explicit redistribute`: ユーザーが明示的に選ぶ既存候補への按分

自動で既存候補へ按分することは禁止します。未配分確率を隠す正規化は、候補漏れや例外を見えなくします。

Hard prune warning threshold:

- 5%超: info
- 15%以上: warning
- 25%以上: hard prune warning
- residual mass がある状態で `hard_prune`: warning

## 8. Reading Drawer

Reading Drawer は、未配分確率が残ったときに追加候補を探すローカルcatalogです。

カテゴリ:

- 副露意図
- 打点パターン
- 進行度
- 待ち・形
- 危険牌・安全度
- 点数状況
- 卓上動態
- 相手傾向
- 例外・ノイズ

危険牌・安全度、点数状況、卓上動態は、Phase1では行動判断材料ではありません。読み候補、文脈タグ、観測候補、例外候補として扱います。

Reading Drawer から候補追加する場合、候補は必要に応じて4軸影響を持てます。ただし4軸影響は行動推奨ではなく、Reasoning Labでの影響分析に接続するためのものです。

## 9. Exception Library

Exception Library は、未配分確率から出た例外候補を保存する補助パネルです。

例外集に入れる候補は、将来候補化できる読みの素材として扱います。例外集は押し引き判断の抜け道ではありません。

保存例:

- `type: exception`
- tags: `exception`, `residual_mass`, `reading_drawer`
- `posterior_probability` / `base_weight`: 未配分から割り当てた確率

## 10. Probability Workbench

Probability Workbench は probabilistic layer の候補確率、ロック、正規化、伝播プレビューを扱います。

Phase1の確率は読み候補空間の整理に使います。押し引きEV、牌選択EV、順位点EVの計算結果として表示してはいけません。

## 11. Reasoning Lab

Reasoning Lab は concentration、pruning impact、lock analysis、ambiguity、reading utility、reading chain、teaching log を確認します。

Reading utility は、読みが候補集中、曖昧性低減、観測計画、未配分低減へどれだけ効いたかを見る派生指標です。勝敗結果や正解率ではありません。

## 12. JSON I/O

Workspace export は `mahjong-knowledge-map.workspace.v4` を維持します。

Subgraph export は `pruning-ui.subgraph.v4` を維持します。

Reading Probability Core で追加した概念は、既存 schema v4 の範囲で保存します。schema互換性を壊さないため、新規必須フィールドは追加しません。

## 13. Warning Rules

Warning rules:

- impactWeight >= 60 かつ axisConfidence <= 40: 過大反映警告
- `mixed` / `unknown` の軸が残る状態で `hard_prune`: downweight / keep top-k の検討を促す
- residual mass が残る状態で `hard_prune`: warning
- rescue rate / table dynamics の `q_total` が大きい: 上限レンジとして扱う警告
- 既存候補への自動按分: 禁止

表示方針:

- 候補確率と未配分確率は%表示
- 影響ウェイトと軸確信度は `70/100` 表示
- 卓上動態 / 他家介入読みは行動推奨ではないと明記

## 14. Tests

最低限確認する観点:

- Quick Reading Inputで4軸影響ウェイトを入力しても、合計100制約がない。
- 影響ウェイトと候補確率がUI上で別単位として表示される。
- 候補確率合計が100未満の場合、residual massが表示される。
- residual massがある状態でhard pruneを選ぶと警告が出る。
- Reading Drawerから候補追加できる。
- Reading Drawerから例外集に送れる。
- 卓上動態カテゴリが行動推奨として表示されない。
- READMEとscriptsのPDF生成コマンドが一致している。
- `docs/requirements-definition.md` と `docs/detailed-specification.md` が存在する。
- `npm run build`、`npm run test`、`npm run lint` が通る。

## 15. 候補木ビュー

候補木ビューは、Reading Probability Core の候補グループ、候補ノード、確率レイヤー、影響レイヤー、未配分候補、例外候補、読みの枝候補を木構造風に投影する表示です。内部データはDAGまたはグラフのままでよく、候補木ビューは保存schemaを変更しない派生表示です。

候補木ビューの用語はユーザー操作に合わせます。候補除外は `枝を切る`、重み低下は `枝を弱める`、上位候補保持は `有力枝を残す`、固定系は `枝を固定する`、`比率を固定する` と表示します。未配分確率は `未展開の枝`、例外は `例外の枝置き場`、候補追加元は `読みの枝候補` とします。

候補木ビュー全体:

```text
+--------------------------------------------------------------+
| 候補木ビュー  [現在のシート] [現在のプロジェクト] [全体]       |
| 読み候補、候補確率、4軸影響、未展開の枝、例外の枝置き場       |
+----------------------+----------------------+----------------+
| 候補木               | 選択した枝           | 枝操作         |
| - 候補グループ       | 候補確率             | 枝を弱める     |
|   - 候補枝           | 入力確率/計算後確率  | 枝を切る       |
|     - 4軸影響        | 影響スコア           | 有力枝を残す   |
| - 未展開の枝         | 軸確信度             | 枝を固定する   |
| - 例外の枝置き場     | 観測/例外/履歴       | 比率を固定する |
+----------------------+----------------------+----------------+
| 反映前確認: 操作前後の差分、変更枝数、警告                   |
| [反映前確認] [反映する] [元に戻す]                            |
+--------------------------------------------------------------+
```

枝を選択した状態:

```text
+----------------------+---------------------------------------+
| 候補木               | 選択した枝: 染め本線                 |
| > 染め本線           | 候補確率 55%                         |
|   速度副露           | 影響スコア 打点 80/100               |
|   役牌バック         | 軸確信度 打点 70/100                 |
|   未展開の枝         | 観測: 同色副露、手出し字牌           |
+----------------------+---------------------------------------+
| 警告: mixed/unknownや未展開の枝が残る場合、枝を切る前に確認  |
+--------------------------------------------------------------+
```

候補木ビューは Sheet / Project / Workspace のスコープ切替に対応します。Sheetではactive Sheetだけ、Projectではactive Project配下、Workspaceでは全体を候補木に投影します。テンプレートから作成された `牌理`、`枚数`、`手役`、`抽象的な読み` は初期枝として表示します。ただしこれらは推奨手順や自動判断ではなく、読み候補を整理する初期素材です。

`枝を切る` を選択した場合は、mixed / unknown の軸、未展開の枝、未知の枝、例外の枝置き場、低い軸確信度、固定中の枝との矛盾を警告します。警告がある場合でも、候補木ビューは保存済みグラフを直接変更せず、反映前確認に見込みを表示します。

現行の候補木ビューは読み候補の投影、枝選択、操作種別の選択、警告プレビューまでです。`反映前確認` / `反映する` / `元に戻す`、未展開・例外への送信、読みの枝候補から追加するボタンにはworkspace mutationを接続していません。実データの確率編集、伝播preview適用、枝刈り記録は詳細編集またはReasoning Labで扱います。

テストでは次を確認します。

- 候補グループが木構造風に表示される。
- 候補確率、影響スコア、軸確信度が枝詳細に表示される。
- 未配分確率が `未展開の枝` として表示される。
- 例外候補が `例外の枝置き場` として表示される。
- 候補木ビュー内に英語の除外操作名が出ない。
- `枝を切る`、`枝を弱める`、`有力枝を残す` が内部 `PruningActionType` の表示ラベルへ対応している。
- mixed / unknown / 未展開の枝が残る状態で `枝を切る` を選ぶと警告が出る。
- Sheet / Project / Workspace のスコープを切り替えられる。
- テンプレート作成枝が初期枝として表示される。
- README、要件定義、詳細仕様、ユーザー向けPDFに候補木ビューが反映されている。

## 16. Future Phase

Phase2以降で扱う可能性があるもの:

- 押し引き判断支援
- 牌選択支援
- 局収支EV
- 順位点EV
- 牌譜parser
- 本格的な確率モデル
- pruning-ui 本体
- 観点横断補正時の未展開・例外確率の再配分

これらは Reading Probability Core の出力を入力として使う別レイヤーであり、Phase1に混ぜません。

### 今後の課題: 観点横断補正時の未展開・例外確率

現行Phaseでは、牌理読み、枚数読み、手役読み、抽象的な読みは、それぞれ別の候補木・別の100%空間として扱います。候補木間で入力確率を自動的に混ぜず、未配分確率、例外集、未知バッファも観点ごとに保持します。4軸影響スコアは候補確率ではなく、その読みが正しい場合に軸をどれだけ動かすかの影響スコアです。

将来的な観点横断補正では、ある観点の読みが別観点の候補分布を変える可能性があります。例として、手役読み候補木で手役A 40%、手役B 40%、未展開・例外 20% の状態から、抽象的な読みの影響で手役Aが薄く手役Bが濃いと見る場合、横断補正後の表示は手役A 10%、手役B 70%、未展開・例外 20% のように変化しうる。ただし、手役Aから抜けた確率質量を常に手役Bへ寄せるとは限りません。

既存候補の説明力が低い、有力候補が少数しかない、mixed / unknown が残っている、部分的な牌姿パターン照合が不足している、抽象読みは濃いが対応する具体的な牌理・手役候補が未定義、候補Aが薄くなったが候補Bへ寄せる根拠も十分ではない、低頻度・高損失パターンを例外候補として保持したい、という場合は、未展開の枝、例外の枝置き場、未知バッファへ確率質量を戻すほうが妥当な可能性があります。

Phase1では、この処理を実装しません。未展開・例外確率を横断補正で自動的に増減させるロジックは入れません。横断補正後の分布を入力確率へ上書きしません。抽象読みだけで既存候補を自動的に大きく切りません。牌姿パターン照合なしで横断統合を確定値として扱いません。4軸影響スコアを候補確率100%に混ぜません。

将来検討する仕様は次の通りです。

- 横断補正後に未展開・例外・未知バッファの確率を増減させる仕組み。
- 既存候補へ再配分するか、未展開・例外へ逃がすかを選ぶUI。
- 有力候補の数、説明力、軸確信度、mixed / unknown、未配分率に応じた再配分ルール。
- 「候補Aが薄くなった分を候補Bに寄せる」のか、「未展開・例外に戻す」のかを区別するプレビュー。
- 横断補正ルールごとの信頼度と統合後分布への影響ログ。
- 部分的な牌姿パターン照合による補正妥当性の検証。
- 統合後分布で、入力確率、枚数補正後重み、横断補正後重み、計算用確率、未展開・例外確率を分離表示すること。

この課題は、将来の pruning-ui / 確率木編集UIで扱う補正設計です。現在の候補木ビューは、観点別候補木の表示と枝操作のプレビューに留めます。

## Project / Sheet 詳細仕様

### Data Model

`WorkspaceDocument` は既存top-level配列を維持したまま、`projects`、`sheets`、`active_project_id`、`active_sheet_id`、`global_settings` を持ちます。Projectは研究テーマや用途の単位で、SheetはProject内の作業面です。Sheetは `node_ids`、`edge_ids`、`case_ids`、`rule_ids`、`saved_view_ids`、`reading_drawer_item_ids`、`exception_node_ids`、`residual_group_ids` を持ちます。

既存workspace v4をnormalizeする場合、Project/SheetがなければDefault ProjectとDefault Sheetを作ります。既存のノード、エッジ、case、rule、saved viewはDefault Sheetへ所属させます。active project / active sheet が不正な場合は、存在するProject/Sheetへ補正します。

### Global Settings

Global Settings は `project_creation_defaults` と `sheet_creation_defaults` を持ちます。各値は `tile_efficiency`、`tile_count`、`yaku`、`abstract_reading` のbooleanです。初期値はすべてtrueです。`create_empty_project_by_default` と `create_empty_sheet_by_default` がtrueの場合、作成ダイアログでは空作成を既定にします。

### Template Catalog

TemplateCatalog は `牌理`、`枚数`、`手役`、`抽象的な読み` を提供します。テンプレートは初期ノード、初期influence edge、Reading Drawer候補、Exception Library候補、Residual Mass候補を作ります。生成物にはtemplate keyを追跡できるtagまたはmetadataを付けます。テンプレートは Reading Probability Core の初期素材であり、押し引き判断、牌選択AI、EV計算、Action Recommendationではありません。

同じSheetへ同じテンプレートを適用する処理はidempotentです。`template_source.enabled_template_keys` に適用済みのkeyを保存し、明示的な再適用を除いて重複配置を避けます。

### UI Flow

App shellにはProject Selector、Sheet Selector、Project作成、Sheet作成、Global Settings、表示スコープ切替を置きます。Project作成ダイアログはProject名、説明、タグ、初期Sheet作成、初期Sheet名、テンプレート選択、空作成を扱います。Sheet作成ダイアログは所属Project、Sheet名、説明、タグ、テンプレート選択、空作成を扱います。

表示スコープは Sheet / Project / Workspace です。Knowledge Mapはscopeに応じてノードとエッジを絞ります。Case Workspaceはactive Sheetに属するcaseを優先し、候補ノードはactive Sheet、active Project、Workspaceの順に優先します。Reading DrawerとException Libraryはscope badgeを表示します。

Residual Mass panelは未配分候補の送信先としてactive Sheet / Project / Global / unknown bufferを選ぶUIを持ちます。ただし現行では選択値をpanel内stateにだけ保持し、追加・未知保持handlerへ渡しません。新規要素の所属は既存store actionによりactive Sheetになります。Project / Globalへの実ルーティングは将来接続です。

### Export / Import

workspace JSON export/importはProject/Sheet/Global Settingsを含みます。subgraph exportは選択中ノードだけでなく、active Sheet、active Project、Workspace全体から対象を選べます。import時はzod schemaで検証し、normalizeでDefault Project/Sheet migrationを行います。

### Score Semantics

4軸は排他的候補ではありません。影響ウェイトは各軸独立の0〜100スコアで、候補確率ではありません。4軸の合計を100にする必要はありません。軸確信度も0〜100スコアです。候補確率と未配分確率だけを%表示します。内部保存では `magnitude` と `confidence` を0〜1として維持します。

## 17. 画面仕様

共通フレーム、目的別ナビゲーション、各画面のカラム構成、空・警告状態、現行の操作制約は [screen-specification.md](./screen-specification.md) を正本とします。
