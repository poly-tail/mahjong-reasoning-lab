# Focused Pruning Canvas 仕様

## 3. プロダクト目的・範囲

名称：Focused Pruning Canvas
副題：競合仮説・成立条件・薄まり理由を編集して比較する試作UI
表示言語：日本語
主対象：PCでの研究・牌譜検討。実戦中のリアルタイム支援は対象外。

検証する体験：
「長文を読む」から「本線を見る → 薄い枝の理由を見る → 条件を変える → 変化を確かめる → 自分の考察を保存する」へ移行できること。
固定デモのスライダーだけで終わらせず、自分の問い・仮説・要因・説明階層を作れること。

今回必須：一画面、単一Board、単一の競合仮説群、基本CRUD、説明メモ階層、AND/OR/NOT条件表示、重み調整、台帳、差分、履歴、自動保存、JSONと専用Markdownの往復。

今回の階層は「説明の階層」。説明メモの子を確率分岐と解釈しない。
複数choice group、階層ごとの条件付き確率、子配分の乗算伝播は次版。データ型だけ先取りして実装しない。
既存4軸は将来の影響先として記録するが、この試作に評価器を追加しない。

## 4. 技術・コマンド・再現性

採用：React、TypeScript、Vite、Zustand、Zod、@xyflow/react、Vitest、React Testing Library、Playwright、ESLint、Prettier。
通常CSSを基本とする。アイコンはlucide-reactを使用可。デザインフレームワークや大規模自動配置は不要。
バックエンド、LLM API、外部フォント、画像生成、CDN配信は使わない。

初期導入時に、利用可能なNodeと各パッケージのengines/peerDependenciesを確認して互換バージョンを選ぶ。
架空の最新版番号を固定しない。決定したNode/npm、主要依存、lockfileを記録する。
Nodeを勝手にグローバル更新しない。互換性不足なら安全な代替またはblocked理由を示す。

npm scriptsを実装する：

- `start` / `dev`：Vite起動。
- `typecheck`：アプリ、テスト、設定ファイルの型検査。
- `lint`：ESLint。
- `format:check` / `format`：Prettierの確認/修正。
- `test` / `test:watch`：Vitestの一回実行/watch。
- `test:e2e`：Playwright Chromium。
- `build` / `preview`：本番ビルド/確認。
- `check`：typecheck → lint → format:check → test → build。失敗時は非0で終了。

通常起動は `npm start`。毎回npm installを要求しない。
lockfile作成後の再現環境・CIは `npm ci`。
ローカル開発サーバは既定でlocalhostへ限定し、意図せずLANへ公開しない。
Windows PowerShellとLinuxでREADMEの手順を利用可能にする。
必要なら `scripts/*.mjs` を使い、npm scriptsへrm/cpやUnix専用環境変数設定を埋め込まない。

## 5. ディレクトリと依存方向

以下は責務の配置。小さいファイルを機械的にすべて作る必要はないが、責務は維持する。

```text
AGENTS.md
README.md
package.json
package-lock.json
index.html
vite.config.ts
vitest.config.ts
playwright.config.ts
eslint.config.js
tsconfig*.json
.gitignore
.editorconfig
.github/workflows/ci.yml

docs/
  spec.md
  acceptance.md
  source-material.md
  exec-plan.md
  design-decisions.md
  change-audit.md
  reference-review.md
  verification.md

src/
  main.tsx
  app/
    App.tsx
    AppLayout.tsx
    createApplication.ts
  domain/
    model.ts
    schema.ts
    validation.ts
    gates.ts
    scoring.ts
    redundancy.ts
    explanations.ts
    deltas.ts
    commands.ts
  application/
    boardStore.ts
    history.ts
    persistence.ts
    ports.ts
    selectors.ts
  infrastructure/
    LocalStorageRepository.ts
    jsonTransfer.ts
    markdownTransfer.ts
    browserFiles.ts
  seed/
    ponDiscardCase.ts
    sourceMaterial.ts
  features/
    canvas/
      FocusedPruningCanvas.tsx
      graphAdapter.ts
      laneLayout.ts
      nodes/
      edges/
    outline/
      OutlinePanel.tsx
      OutlineKeyboard.ts
    inspector/
      InspectorPanel.tsx
      ContributionLedger.tsx
      GateInspector.tsx
    timeline/
      TimelinePanel.tsx
    toolbar/
      Toolbar.tsx
  shared/
    ui/
      ErrorBoundary.tsx
      ConfirmDialog.tsx
      FormField.tsx
    styles/
      tokens.css
      app.css

tests/
  unit/
  component/
  e2e/
  fixtures/
  setup.ts
```

依存方向：features → application → domain。infrastructure → domain/ports。appで具象を組み立てる。
applicationからLocalStorageRepositoryの具象を直接importしない。
`shared`を雑多な業務ロジックの置き場にしない。
React FlowのNode/EdgeはgraphAdapterで生成する表示モデルであり、保存正本ではない。

一画面/一storeへ全責務を詰めない。App約150行、store約300行、画面部品約350行は分割検討の目安。
行数だけで合否にせず、越えるときは責務上の理由を記録する。1,000行級の集約ファイルは避ける。

## 6. データ契約

Zod schemaを保存境界の正本とし、可能な型はz.inferで導出する。再帰型など必要な部分だけ明示型を併用する。

BoardDocumentに保存するもの：

- id、title、question、classificationAssumption。
- hypotheses、factors、effects、evidenceGroups、gates、notes。
- sourceMaterialsと各要素のsourceRefs。
- modelConfig、decisionMemo、reflectionMemo。

### Hypothesis

id、label、baseScore、manualAdjustment、manualPruned、mustKeep、residual、decisionImpact、riskNote。
decisionImpactは0～100の主観的重要度。損失額・EV・確率として解釈せず、スコア計算へ入れない。
`downweighted`はmanualAdjustment < 0から導出する。statusと同じ値を二重保存しない。
`mustKeep`は手動削除/pruneを防ぐ保護であり、配分の下限保証でも数値ロックでもない。

### Factor

id、label、kind、state、confidence、opportunity、verification、sourceRefs。

- kind：observation / assumption / model_rule。
- state：present / absent / unknown / unobservable。
- confidence：0～1。入力者が付ける根拠信頼度であり、真である確率とは断定しない。
- opportunity：yes / no / unknown。イベント観測のときだけ使用する。
- verification：unverified / verified。hard gateで使用可能な根拠を区別する。

推定上の「聴牌ではない」を、観測機会後の「ラグがなかった」と同じ型の意味にしない。
kind=observationかつstate=absentならopportunity=yesを必要とする。
no/unknownなら否定の証拠として適用せず、条件評価unknownと警告を返す。入力値は無断で改変しない。
confidence=0、unknown、unobservableは数値寄与0かつ条件葉の評価unknown。unknownをfalseへ変換しない。

### Effect

id、factorId、hypothesisId、strength、applicabilityConfidence、activeStates、when、evidenceGroupId、sourceRefs。
strengthは-2～+2。符号を方向の正本とする。
supports/weakensは符号から表示用に導出し、食い違うrelationを別保存しない。
applicabilityConfidenceは「その根拠をこの仮説へ適用する強さの信頼度」で0～1、既定1。
同じ不確実性をfactor confidenceと両方で下げない。二つとも変更するときは説明を残す。
whenは任意のGateExpressionで、その効果を適用する文脈。省略時true。

### EvidenceGroup

id、label、aggregation、rationale。
aggregation=maxAbs / mean / sum。既定maxAbs。
これは入力者が同根・重複と判断した寄与を束ねる便宜的規則であり、統計的相関の推定器ではない。
同一group内でも集約は仮説別に行う。
maxAbs/meanの同時有効メンバーに正負が混在するときは、勝手に片方を採用せずvalidation errorとする。
sumは入力者が別根拠の加算を意図した場合だけ使い、rationaleを必須にする。

### Note

id、ownerHypothesisId、parentNoteId、order、label、body、sourceRefs。
同じ仮説に属するNote同士だけ親子化可能。最大深さ6、循環禁止。
Noteは説明であり、追加・字下げだけでは重みを変えない。
メモを数値要因にしたい場合はFactorを作成してEffectを接続する。

### GateExpression

```ts
type GateExpression =
  | { kind: 'condition'; factorId: string; is: 'present' | 'absent' }
  | { kind: 'all'; children: GateExpression[] }
  | { kind: 'any'; children: GateExpression[] }
  | { kind: 'not'; child: GateExpression };
```

Gate：id、hypothesisId、expression、mode、falsePenalty、evidenceGroupId、explanation。
mode：informational / soft / hard。
ゲートの評価木と数値寄与を分ける。条件に使ったこと自体では加点・減点しない。

### 正本と派生値

rawScore、displayShare、ゲート評価、寄与台帳、React Flow座標は評価・表示時に導出する。
保存済みの過去の配分を次回のbaseScoreに流用しない。
色、選択、折り畳み、zoomはUI状態。計算へ影響させない。
任意ドラッグ座標の保存は不要。orderから決定論的に配置する。

## 7. 計算規則・不変条件

### 7.1 有効寄与

Factorの観測条件が有効、stateがactiveStatesに含まれる、when=trueのときだけ適用する。
when=false/unknownは寄与0にし、それぞれ「適用条件不成立」「適用条件未確定」を台帳へ残す。

```text
rawContribution = strength × factor.confidence × applicabilityConfidence
```

同一要因への重複Effectは、factorId・hypothesisId・activeStates・whenが同じなら登録拒否する。
異なるwhenの重なりまで自動証明しない。重複可能性は警告・同根グループで扱う。

### 7.2 同根グループ集約

数値効果とsoft gate penaltyを共通の寄与候補として扱う。
同一evidenceGroupId × hypothesisIdで集約する。

- maxAbs：絶対値最大の一件だけ適用。同値は固定ID順。その他は0と抑制理由を記録。
- mean：有効メンバーn件の各寄与を1/nとして台帳へ割り当てる。未適用要因を分母へ入れない。
- sum：加算。
- groupなし：独立に適用。ただし独立性を証明したことにはならない。

同じ根拠を表すgate penaltyとeffectを併用するなら同一groupに束ねる。
デモのゲートはinformationalにして、既に効果に使っている理由を再減点しない。

### 7.3 raw score

```text
rawScore(h) = baseScore(h)
            + scoreScale × sum(appliedContributions(h))
            + manualAdjustment(h)
```

modelConfig：scoreScale=0.5、temperature=1.0を初期値として保存する。
scoreScaleは全候補共通。候補ごとに都合よく変えない。
baseScore/manualAdjustmentは-5～+5、strengthは-2～+2、temperatureは0.5～3、scoreScaleは0.1～1。
通常画面でtemperatureを調整させる必要はないが、保存/importした設定は評価へ反映する。

「弱める」操作はmanualAdjustment=-1に設定する冪等操作。連打で-2、-3にしない。
「復元」はmanualPruned=falseとmanualAdjustment=0を一操作で行い、baseScoreや根拠は変更しない。
数値の直接編集は別フォームで行う。

### 7.4 配分

included = 手動pruneされていない AND hard gateで確定falseではない。
対象候補のx=rawScore/temperature、m=max(x)として安定化softmaxを使う。

```text
displayShare(h) = exp(x(h)-m) / sum(exp(x(j)-m))
```

除外候補はdisplayShare=0。InfinityやNaNをUI・保存データへ出さない。
丸めは表示時だけ。内部評価は丸めない。表示は小数1桁程度、微小な正値は「0%」ではなく「<0.1%」。
表示名は「相対配分（未校正）」。分類仮定と仮置き重みに依存し、実測確率ではないと常時示す。

residualは必ず一つ、mustKeep=true、manualPruned=false、gate設定不可。
全候補除外・residual欠損は不正データとして拒否する。「自動的に例外100%」へ改変しない。
正当な操作で通常候補が全て除外され、residualだけが残った場合は100%で正常。
例外枝の存在は未知ケースの真の確率や網羅性を保証しない。

## 8. ゲートの三値論理と保護枝

all：一つでもfalseならfalse、全部trueならtrue、他unknown。
any：一つでもtrueならtrue、全部falseならfalse、他unknown。
not：true/false反転、unknown維持。
空のall/any、参照不明、深さ8超、条件木循環は不正。

informational：評価だけ表示、数値寄与0。
soft：falseならfalsePenalty（負値）を寄与候補へ、unknownなら0＋未確定警告。
hard：falseなら計算対象外、unknownなら残す。

hard評価ではverification=verifiedかつconfidence=1の条件だけを真偽確定に使う。それ以外の葉はunknown。
verifiedは利用者の明示的な確認情報であって、アプリが正しさを保証したという意味ではない。
麻雀の「普通はしない」「ほとんどない」はhard gateの根拠にしない。

mustKeepは手動prune/削除を禁止するが、確定したhard falseを無効化しない。
hard falseになった保護枝は、配分0でカードを表示し「保護対象だが条件不成立」と説明する。
折り畳みは表示操作だけで計算対象外にしない。
低配分の自動prune、top-k除外、数値固定lockは今回は実装しない。

Gate編集は検証済みプリセットの表示と条件値の変更を中心とする。
再帰式はJSON/専用Markdownで保持・読込可能にするが、高機能な任意条件ツリーGUIは作らない。
Effectのwhenも表示・保存・検証し、初版のGUIはプリセット利用と基本フォームに限定する。

## 9. 説明台帳・変化の説明

評価関数は各候補について、少なくとも以下を返す。
base、effect、inactive、unknown、group_suppressed、gate、manual、finalScore、normalizationSummary。
各項目はid、sourceId、hypothesisId、label、rawValue、appliedValue、理由、単位を持つ。
正規化は非線形なので「スコア加算行」として扱わず、分母・対象集合を別サマリーにする。
台帳の適用寄与を式へ戻すとrawScoreと一致しなければならない。

「なぜ薄いか」は現在有効な負寄与の強い順に上位3件。
「何が支持しているか」「適用されなかった理由」「同根抑制」「条件未確定」は別枠。
低いbaseScore、手動調整、soft gateの減点も理由に含め、要因効果だけを説明して終えない。
「何なら復活するか」は明示された成立条件・未成立の適用条件を列挙する。最小変更集合を最適化したと主張しない。

直前の意味的操作のbefore/afterを比較し、rawScoreDeltaとshareDeltaを別表示する。
自身が変わらず他候補だけ下がった場合は「競合候補低下による相対上昇」。
自身のスコア上昇を、必ず「直接証拠」と呼ばない。手動調整なら手動調整、基準変更なら基準変更と書く。

数値分解を実装する場合は、候補iと他候補全体の二群に限定し、次の対称分解を使う。
f(a,b)=候補iの入力a、他候補の入力bから計算したiの配分。入力にはrawScoreとincludedを含む。
0=before、1=after。

```text
ownEffect = ((f(1,0)-f(0,0)) + (f(1,1)-f(0,1))) / 2
otherEffect = ((f(0,1)-f(0,0)) + (f(1,1)-f(1,0))) / 2
ownEffect + otherEffect = shareAfter - shareBefore
```

これはモデル内の配分変化の分解であり、現実の因果効果の推定ではない。
候補数・ID集合・modelConfigが変わる操作では無理に分解せず「構造/モデル設定変更」と表示する。
他候補それぞれへの％寄与を、その候補のshareDeltaから捏造しない。rawScoreDeltaと除外状態の変化だけ列挙する。
上記の分解は実装対象とし、受入テストで合計一致を確認する。

## 10. ゴールデンケース

問い：「ポン出し関連牌は、どの手牌構造から出たのか」
画面に「デモ用仮置きモデル」「麻雀理論・頻度は未検証」と表示する。
分類は同一の問いへの競合候補として仮置きし、重なりがないと実証したとは書かない。
H3はH4のリャンカン由来を含めない分類注記を付ける。

| ID  | 仮説                           | baseScore | decisionImpact | 保護               |
| --- | ------------------------------ | --------: | -------------: | ------------------ |
| H1  | 近くの対子・雀頭固定           |       0.4 |             65 | なし               |
| H2  | 両面固定                       |       0.1 |             95 | mustKeep           |
| H3  | 対子フォローからカンチャン固定 |      -0.5 |             45 | なし               |
| H4  | リャンカンからカンチャン固定   |      -0.3 |             60 | なし               |
| H5  | その他・例外                   |      -0.8 |             80 | residual、mustKeep |

H3の説明にユーザー表現「シャンポン→カンチャン固定」を残す。
H2.riskNote：「赤跨ぎ等の高打点ケースは、薄くても見落とさない。打点は仮説・未検証。」
manualAdjustmentは全て0。manualPrunedは全てfalse。

### Factor一覧

P/A/Uはpresent/absent/unknown。Cはconfidence。
特記なきverificationはunverified、sourceはユーザー仮説をseed化したものとする。

| ID  | 内容                                       | kind        | state |   C |
| --- | ------------------------------------------ | ----------- | ----- | --: |
| F1  | 関連牌構成率を対子固定支持と評価           | model_rule  | P     | 0.6 |
| F2  | ブロックが狭い                             | assumption  | P     | 0.7 |
| F3  | XY周辺に構成余地がある                     | assumption  | A     | 0.7 |
| F4  | 字牌雀頭候補が十分にある                   | assumption  | A     | 0.7 |
| F5  | 聴牌している                               | assumption  | A     | 0.8 |
| F6  | 3飜以上の高打点が見込める                  | assumption  | A     | 0.7 |
| F7  | 安い非聴牌での発進動機は弱い               | model_rule  | P     | 0.6 |
| F8  | チートイ・対々和等の代替ルートへ逃げやすい | model_rule  | P     | 0.6 |
| F9  | 対子をポン材として保持する価値がある       | model_rule  | P     | 0.7 |
| F10 | 役牌から発進した                           | assumption  | A     | 0.7 |
| F11 | 非役牌の愚形発進レンジが狭い               | model_rule  | P     | 0.6 |
| F12 | ドラに反応した                             | observation | U     | 0.6 |
| F13 | 鳴きのラグがあった                         | observation | U     | 0.5 |
| F14 | 赤赤の構成が否定された                     | assumption  | U     | 0.6 |
| F15 | 役牌バック条件が成立する                   | assumption  | U     | 0.7 |
| F16 | その後に手出しが入った                     | observation | U     | 0.7 |

観測イベントのopportunityは初期unknown。
「聴牌」と「非聴牌」は別変数にせず、F5のpresent/absentで表現する。
初期Aは安手・非聴牌を仮定した比較シナリオであり、実際の対局で確定した観測ではない。

### Effect一覧

applicabilityConfidenceは全て1。F13だけ0.6。
「非聴牌安手」はF5=A AND F6=A。

| source→target | activeStates | strength | when       | group |
| ------------- | ------------ | -------: | ---------- | ----- |
| F1→H1         | P            |       +1 | true       | なし  |
| F2→H2         | P            |       -1 | true       | G1    |
| F3→H2         | A            |       -2 | true       | G1    |
| F4→H2         | A            |       -1 | true       | G1    |
| F5→H2         | P            |       +2 | true       | なし  |
| F6→H2         | P            |       +2 | true       | なし  |
| F7→H2         | P            |       -1 | 非聴牌安手 | G2    |
| F8→H2         | P            |       -2 | 非聴牌安手 | G2    |
| F8→H3         | P            |       -1 | F5=A       | なし  |
| F9→H3         | P            |       -2 | true       | なし  |
| F10→H4        | P            |       +2 | true       | なし  |
| F11→H4        | P            |     -1.5 | F10=A      | なし  |
| F12→H2        | A            |       -1 | F5=A       | G3    |
| F13→H2        | A            |     -0.5 | F5=A       | G3    |
| F14→H2        | P            |       -1 | F5=A       | なし  |

G1=構成自由度不足、G2=安手非聴牌の発進選択、G3=鳴き反応の不在。同根仮定、全てmaxAbs。
G3が同一機会の観測でない場合は同根とは限らないため、説明に仮定を明記する。
F16は説明上保持するが数値Effectなし。「手出しがあれば必ず非聴牌」と自動判定しない。

### Gateプリセット

H2：F5=P OR (F5=A AND F3=P AND F6=P)。mode=informational。
H4：F10=P OR F15=P。mode=informational。
これらはユーザー仮説の説明用簡略化であり、麻雀上の必要十分条件の証明ではない。
soft/hardはエンジンとfixtureで試験するが、未検証のこのseedをhardにしない。

### 説明メモ

H2には、聴牌/非聴牌、構成余地、Xが字牌の場合、ドラドラ、赤跨ぎ、安手で別ルートへ移る理由、後続観測、役制約の階層を作る。
H3には、2対子/3対子、ポン材価値、チートイ・対々和への逃げを作る。
H4には、初副露/2副露目、役牌発進/非役牌愚形発進、役牌バック、残る例外を作る。
原文の役確定/未確定、全体役、片アガリ、形式聴牌、空切りスライドなどをNoteに残す。未実装の数値寄与を捏造しない。
H5には、未分類・未知例外、観測ミス、相手依存のレンジ差を置く。
各メモからsourceMaterialへ戻れるようにする。

### 初期値とシナリオ検証

初期rawScoreは H1=0.7、H2=-1.2、H3=-1.5、H4=-0.75、H5=-0.8 になる。
これをunit testで確認する。初期配分の期待値は別途計算し、上記式との一致も試験する。
UI用の合格範囲：H1が最大かつ40～70%、H2が5～20%、H3<H4、H5が5%以上。
実測値へ合わせるテストではなく、比較が視認できるデモ設計のテストである。

F5=P、続いてF6=Pへ変更すると、H2は初期より15ポイント以上上昇し、30%以上になること。
F7/F8の「安手非聴牌」効果は適用外となり、古い前提の減点が残らないこと。
F12=A/opportunity=noでは減点せず、yesへ変更した場合だけ文脈に応じて適用すること。

## 11. 編集機能とキーボード

必須CRUD：問い・仮説・要因・説明メモの作成/編集/削除、FactorとHypothesisの基本接続/解除。
通常仮説のbaseScore、manualAdjustment、decisionImpact、riskNote、mustKeepを編集可能にする。
prunedの通常仮説を保護したい場合は先に復元を要求し、矛盾状態を作らない。残余の保護は解除不可。
Effectは接続先、strength、activeStates、applicabilityConfidenceをフォームで編集できること。
複雑なwhenは読取表示とimport対応。自由線引きだけに依存せず、ドロップダウンで接続できること。
EvidenceGroupは既存groupへの割当/解除と新規同根group作成を可能にする。

「空のBoard」は問いとH5相当の残余枝だけを作成する。ユーザーが通常仮説と要因を追加できること。
単一Board方式であり、Board一覧やProject管理は作らない。

Outlineの操作：

- 通常のラベル編集中Enter：確定して同種の兄弟項目を追加。
- Escape：編集を取り消す。
- 説明メモの構造編集モードでTab：直前の兄弟Noteの子へ移動。
- Shift+Tab：親Noteの兄弟へ戻す。
- Hypothesis/FactorでTabを押して別種の親子へ変換しない。
- 選択行のCtrl/Cmd+Delete：削除確認。編集中のDeleteは通常の文字削除。
- Ctrl/Cmd+Z、Ctrl/Cmd+Shift+Z、WindowsのCtrl+Y：BoardのUndo/Redo。ただしテキスト編集中はブラウザの文字編集Undoを優先。

構造編集モードは明示トグルと説明を持ち、Escで抜ける。通常のTabによるフォーカス移動を全画面で奪わない。
IME変換中はisComposingおよびcompositionイベントを考慮し、Enter/Tabで項目追加しない。
実ブラウザの合成イベントテストだけで日本語IMEの実機検証済みと主張しない。手動確認手順もREADMEへ書く。

削除時は参照関係を事前表示する。
Factorがゲート/whenに使われる場合は削除拒否して参照箇所を示す。参照式を勝手にtrueへ変換しない。
Effectだけに参照されるFactorや通常Hypothesisは、関連Effect/Note/Gateの同時削除範囲を確認して一操作で削除する。
mustKeep/residualは削除不可。Noteは子孫込みの削除を確認する。
無効な字下げ、同値設定、空ラベル確定は履歴を増やさない。

## 12. 画面・表示

一画面：上部Toolbar、左Outline、中央Canvas、右Inspector、下Timeline。
1440×900で主要操作を確認でき、1280pxでもペイン切替で操作可能にする。
min-width:0、適切なmin-height、内部スクロールを設定し、ページ全体の不要な横スクロールを防ぐ。
低幅ではInspector/Outlineを切替式へ落とし、文字を極端に小さくしない。

### Canvas

@xyflow/reactを使い、問い、仮説レーン、選択仮説の要因/ゲートを表示する。
標準は全Effectを同時表示せず、選択仮説の関係を展開する。全展開も可能にする。
ID/orderに基づくlane配置で、スコア変更だけでは位置/並びを変えない。
配分順への自動再ソート、毎編集時のfitView、ノードの飛び回りを禁止する。
fitViewは初回、明示操作、構造変更後の要求時に限定する。

問い→仮説の主枝：配分に応じた線幅。例 `2 + 16×sqrt(share)` px。
視認性のため非線形であることを凡例に示す。正確な比較は線形バーと数値を併記する。
配分0は通常の正値線幅にせず、除外表示とする。カードは消さない。
Factor→仮説の線：支持/弱化/未適用を符号とラベルで区別する。
confidenceの破線等は該当Factor/Effectへ付ける。仮説全体の信頼度を勝手に平均計算しない。
decisionImpactは警告バッジと数値。配分計算へ掛けない。
mustKeep/residualは結論ビューでも確認可能にする。
色だけに意味を依存しない。日本語フォントはシステムフォントを使用する。

### Inspector

仮説：配分、rawScore、base、手動調整、保護/残余、重要度、riskNote、薄まり上位3件、支持要因、台帳、復活条件、差分。
要因：kind/state/confidence/opportunity、適用先、Effect、同根group、根拠原文。
ゲート：AND/OR/NOT木、三値評価、false/unknown原因、mode、数値寄与の有無。
説明メモ：タイトル/本文/階層/根拠原文。

### Toolbar/Timeline

Undo、Redo、新規、デモへ戻す、JSON/Markdown export/import、保存状態、表示密度（結論/標準/全展開）。
pruneはbefore/afterの主要変化と対象を確認して適用できること。
未実装ボタン、押しても変化しないボタンを置かない。
Timelineは後述の履歴正本から表示する。

## 13. コマンド・Undo/Redo・履歴

意味的な編集は必ず単一のコマンド経路を通し、検証に成功した変更だけ確定する。
Reactの再描画、選択、折り畳み、zoomでは編集履歴を追加しない。
入力中のドラフトと確定値を分け、文字入力ごとにsnapshotを増やさない。
スライダーを採用するならpointerup/キー操作の確定単位でcommitする。

保存する履歴は、再帰構造でないflatなsnapshot列とcursorにする。
各snapshot：id、timestamp、actionLabel、BoardDocument。
BoardDocumentの中にhistory/timeline/AppStateを含めない。
現在のdocumentはsnapshots[cursor].documentから取得し、別の正本を二重保持しない。

Undo/Redoはcursor移動。新しい操作ログを再帰的に追加しない。
Undo後の新規編集はfutureを切る。同値/no-opではfutureを切らない。
Timelineはsnapshot列から生成し、直前snapshotとの差分を再計算する。
seedへ戻す/空Boardへ置換は確認後に一操作として追加しUndo可能にする。

保持上限は50snapshot、かつEnvelopeのシリアライズ済みUTF-8サイズ2MiB。
新規編集で超える場合は古いsnapshotから切り、cursorを正しく補正する。現在snapshotは切らない。
BoardDocument単体は512KiBまでとし、超過する編集はエラーで拒否する。
上限と「保存対象は件数・容量内の直近履歴」とREADME/UIへ明記し、短縮時は通知する。完全な永久監査ログと称しない。
古い履歴の削減は入力本文や現在Boardの要因を削ることではない。

## 14. 永続化と失敗時の扱い

初版はlocalStorage。IndexedDB移行のために過剰な抽象化はせず、保存境界だけ分離する。
同期APIとして `load / save / removeOwnData` を持つRepositoryをportsへ定義し、Result型で成否を返す。
UIはlocalStorageを直接呼ばない。Storage実体の取得自体が失敗するケースも捕捉する。

初版はdebounce自動保存を採用しない。意味的操作の確定時に検証・シリアライズして一回保存する。
文字入力中は保存しない。これにより古い遅延保存が新規/リセット/importへ上書きする競合を避ける。
件数・容量上限とサイズ制限で同期保存の負荷を抑える。性能が不足したら計測値を根拠に移行提案を記録する。

Storageキーは本アプリ専用。localStorage.clear()は禁止。
初回にデータがない場合だけseedを生成する。React StrictModeによる二重初期化で増殖しないこと。

破損/未対応version：自動保存を止め、破損データのraw export、再試行、明示的復旧を提供する。
quota/security例外：編集内容をメモリに保持し「未保存」と表示。JSON exportは可能にする。
保存できたときだけ「保存済み」。読み込み前の空状態で既存値を上書きしない。

複数タブ：storageイベントを検知したら、他タブ更新の警告を出し自動保存を停止する。
書込直前にも前回読込/保存したrevisionとStorageのrevisionを照合し、不一致なら上書きしない。
これは完全な多タブ排他制御ではない。localStorageの同時競合は解消せず、共同編集は非対象と記載する。

## 15. 保存形式・JSON/Markdown入出力

保存Envelope：

- schemaVersion：`pruning-canvas.v1`。
- engineVersion：`weighted-score.v1`。
- revision。
- snapshots、cursor。

旧リポジトリのworkspace.v4や前案の別構造のv1は同一schemaとみなさず、未対応として拒否する。
スキーマ形式や意味が変わったらversionを変え、無断の意味変換を行わない。

Zod検証だけでなく、ID重複、存在しない参照、残余数、保護枝の不正状態、Note循環、Gate深さ、設定範囲を検証する。
要素IDは全体で一意とする。構造上の上限は通常仮説50、Factor100、Effect300、Note300、Gate50。
入力ファイル上限5MiB、ラベル120文字、Note本文4,000文字、原文は全sourceMaterials合計64,000文字。
文書512KiB・Envelope 2MiBの上限も検証する。importで超過した履歴は勝手に縮めず拒否する。
編集時の履歴短縮以外の上限超過を黙って切り捨てない。
JSON/Markdownとも全snapshotを検証する。未知フィールドはstrictな境界でエラーとし、無言で消さない。

importは読込 → parse → version → 構造/参照検証 → 置換確認 → 適用。
失敗/キャンセルでは現行Board、履歴、Storageを変えない。
成功時はファイル内の履歴へ置き換える。旧履歴と混ぜず、その旨と事前export導線を確認画面に示す。
保存失敗時は未保存状態と直前状態のメモリ上の退避を保ち、元へ戻す操作を提供する。
revisionはローカル書込競合の検知用メタデータ。import適用時/保存時は新値を発行してよい。
serializer/parser単体の往復は全項目一致、アプリへの取込後の一致対象はrevision以外の文書・履歴・設定とする。

JSONは復元用正本。export直前にも検証する。
Markdownは、人間向け概要＋一つの `pruning-ui-json` fenced blockに同じEnvelopeを埋め込む専用形式。
概要：問い、本線、各配分、主要理由、例外、未確定事項、メモ。原文はJSON内にも保持する。
importは厳密に一つの専用blockだけを復元に使う。汎用Markdownの自然言語解析はしない。
「本文の編集は復元に反映されず、埋込データが正本」とexport文書とimport画面に明記する。
専用blockなし/複数/不正JSONは拒否する。
表示用文字列に含まれる記号は安全にエスケープし、ユーザー本文が偽の専用blockを作らないようにする。

raw HTMLをレンダリングしない。ユーザーラベルを安全でないファイルパスにしない。
Blob URLはダウンロード処理後に解放する。
JSONと専用Markdownのround-tripで、document/history/cursor/config/sourceRefsが保存前後一致すること。

## 16. 非対象・次版へ残す事項

今回作らない：
Project/Sheet、ログイン、クラウド、共同編集、サーバ、LLM、自動文章解析、牌譜解析、正式ベイズ推論、確率校正、EV、押し引き/打牌推奨、4軸評価器、救済率、教材作成、全体Knowledge Map。

次版候補としてdocsへ明記するが、未実装画面を作らない：

- 複数choice groupと階層ごとの確率/重み、局所/周辺配分。
- PDF、PNG、SVGの利用者向け出力。
- 任意の条件ツリーGUI、Effect文脈の高機能編集。
- 固定値lock、freeze ratio、top-k、A/Bを並べたシナリオ比較。
- IndexedDB、巨大Board、永続的全操作監査、スマホ編集。
- 実測校正、個人差モデル、他領域テンプレート。

Markdownは今回の専用形式往復まで実装。一般Markdownを編集して任意グラフへ変換する機能は次版。
UI検証用スクリーンショットの生成は、PNG export機能とは別で今回必須。
