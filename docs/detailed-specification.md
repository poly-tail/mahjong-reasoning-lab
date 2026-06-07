# Mahjong Reasoning Lab 詳細仕様書

作成日: 2026-06-08

## 1. 全体アーキテクチャ

Mahjong Reasoning Lab は React / TypeScript / Vite で実装する local-first アプリです。状態管理は Zustand、永続化は Dexie IndexedDB、データ検証は zod schema を使います。

Phase1 の正式名称は Reading Probability Core です。Phase1 は、観測、読み候補、候補確率、未配分確率、例外候補、4軸影響を整理する層であり、押し引き判断AIや牌選択AIではありません。

主な境界:

- `src/app`: app shell、navigation、Zustand store
- `src/domain`: zod schema、seed、taxonomy、reading numerics、residual mass、drawer catalog
- `src/infrastructure`: IndexedDB、file helpers
- `src/ui`: Case Workspace、Quick Reading Input、Workbench、Lens UI
- `docs`: 要件、仕様、理論、運用ドキュメント

## 2. データモデル

中心データは `WorkspaceDocument` です。workspace v4 互換を維持し、既存フィールドで Reading Probability Core を表現します。

主な要素:

- `KnowledgeNode`: 観測、仮説、metric、choice group、例外、曖昧性など
- `KnowledgeEdge`: semantic / probabilistic / influence / reasoning の関係
- `CaseItem`: active case と attached nodes
- `ReadingImpactDraft`: Quick Reading Input の入力状態
- `ResidualMassSummary`: choice group の未配分確率と扱い
- `ReadingDrawerItem`: 未配分や思い出し漏れから候補化できるcatalog item

schema変更なしで扱うため、未配分や例外は既存の node type、tags、probability fields、pruning hints を組み合わせて保存します。

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

## 15. Future Phase

Phase2以降で扱う可能性があるもの:

- 押し引き判断支援
- 牌選択支援
- 局収支EV
- 順位点EV
- 牌譜parser
- 本格的な確率モデル
- pruning-ui 本体

これらは Reading Probability Core の出力を入力として使う別レイヤーであり、Phase1に混ぜません。
