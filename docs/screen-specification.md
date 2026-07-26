# Mahjong Reasoning Lab 画面仕様書

更新日: 2026-07-26

## 1. 対象と前提

この文書は `src/app/AppShell.tsx` と `src/ui/` の現行画面を正本化します。Phase1 は Reading Probability Core であり、画面は読み候補空間の記録・比較・説明を支援します。押し引き判断、牌選択、EV計算、Action Recommendation は表示しません。

現行レイアウトはデスクトップ優先です。アプリ全体は `h-screen`、最小高さ `720px` を前提とし、主要画面には固定幅を含む複数カラムがあります。狭い画面向けの1カラム化やモバイル専用ナビゲーションは現行スコープ外です。

## 2. 共通フレーム

画面は上から次の順に並びます。

1. ヘッダー
2. エラーバナー（エラー時のみ）
3. Workspace scope bar
4. 目的フレーム
5. 選択中の機能画面
6. Project / Sheet / Global Settings modal（開いている場合）

### 2.1 ヘッダー

左側にはアプリ名 `麻雀思考ラボ` と `schema_version` を表示します。中央には目的別ナビゲーション、右側には履歴・保存操作を置きます。

目的別ナビゲーション:

- `局面で考える`
- `理論を整理する`
- `確率と枝刈り`
- `読みを検証する`
- `教材化する`
- `データ管理`

右側の共通操作:

- 元に戻す: `Ctrl+Z`
- やり直す: `Ctrl+Y` または `Ctrl+Shift+Z`
- 自動保存間隔の選択
- 手動保存: `Ctrl+S`
- 保存状態表示: 読み込み中、未保存、保存中、保存済み、保存エラー

ナビゲーション領域は横方向へ overflow できます。ヘッダー全体をモバイルメニューへ置き換える仕様はありません。

### 2.2 Workspace scope bar

常時表示する操作:

- Project selector
- Sheet selector
- Project作成
- Sheet作成
- 表示スコープ: `Sheet` / `Project` / `Workspace`
- Global Settings

Projectを切り替えた場合は、そのProjectに属する先頭Sheetと先頭caseを選び、ノード・エッジ選択を解除します。Sheetを切り替えた場合もactive Project / Sheet / caseを同期し、選択を解除します。

表示スコープは画面表示とsubgraph exportの絞り込みに使います。`scopeMode` 自体はZustandのUI状態であり、`WorkspaceDocument` の永続フィールドではありません。

### 2.3 作成・設定modal

Project作成modal:

- Project名
- 説明
- タグ
- 初期Sheetを作成するか
- 初期Sheet名
- 初期テンプレート
- 空作成

Sheet作成modal:

- 所属Project
- Sheet名
- 説明
- タグ
- 初期テンプレート
- 空作成

Global Settings modal:

- 新規Projectの既定テンプレート
- 新規Sheetの既定テンプレート
- Project / Sheetを空で作る既定値
- 既定値へ戻す

テンプレートは `牌理`、`枚数`、`手役`、`抽象的な読み` の4種類です。

## 3. 局面で考える

`CaseWorkspace` は3カラムです。

- 左 `360px`: case選択と局面入力
- 中央 `minmax(0, 1fr)`: 思考経路、判断プロセス、未配分、数値反映済みの読み
- 右 `320px`: 関連知識候補と関連付け操作

中央は次の2表示を切り替えます。

- 4列: 観測 / 仮説 / 条件 / 判断
- 判断プロセス: 洗い出し / 重み付け / 加算・合成 / 比較 / 選択 / 反省

active Sheetのcaseを先に並べます。関連知識候補はactive Sheet、active Project、Workspaceの順で優先度を付け、title / tag / edge近傍を使った簡易スコアで並べます。これは自動推論ではありません。

未配分確率サマリには `active sheet` / `Project` / `Global` / `unknown` の送信先選択を表示します。現行実装ではこの選択はパネル内の表示状態だけで、追加・未知保持handlerへ送信先を渡しません。新規要素の実際の所属は既存store actionに従いactive Sheetになります。Project / Globalへの永続ルーティングは将来接続です。

## 4. 理論を整理する

二次タブ:

- `Mapping Inbox`
- `知識マップ`
- `手牌価値`
- `脇救済率`
- `ルール作成`

### 4.1 Mapping Inbox

2カラムです。左で考察メモとテンプレートを選び、右で下書きノード案を確認します。下書きは選択して知識マップのみ、またはactive caseへ関連付けて作成できます。自然言語の自動解析やLLM呼び出しは行いません。

### 4.2 知識マップ

中央をReact Flow canvasとし、左に折りたたみ可能なノードパレット、右に折りたたみ可能なInspectorを置きます。

主な操作:

- ノード作成、接続、移動、複製、削除
- 複数選択とグループ化
- グループ折りたたみ
- 検索、タグ・型フィルタ、Domain Lens
- 保存ビュー
- 凡例とマッピングガイド

表示スコープに含まれるノードと、両端がスコープ内にあるエッジだけを表示します。

### 4.3 手牌価値

4軸を1〜4カラムで表示します。

1. 進行度・聴牌率
2. 打点
3. 待ち・形の良さ
4. 点数状況・行動閾値

4軸は独立した0〜100の影響スコアで、合計100にしません。候補確率として表示しません。

### 4.4 脇救済率

画面見出しは `卓上動態 / 他家介入読み` とし、旧称 `脇救済率` を補助表示します。時間窓、イベントごとの概算確率、`q_total = 1 - product(1 - q_i)`、上限警告を表示します。結果は読み候補であり、押し引きEVや行動推奨ではありません。

### 4.5 ルール作成

Rule Builder Lite は一覧とform editorを表示し、`Hard gate` / `Soft score` / `Override` / `Fallback` を分離します。本格的な条件ツリーeditorは表示しません。

## 5. 確率と枝刈り

二次タブ:

- `確率伝播`
- `影響モデル`
- `枝刈りラボ`

### 5.1 確率伝播

初期表示は候補木ビューです。`候補木ビュー` と `詳細編集` を切り替えられます。

候補木ビューは上部説明、中央3カラム、下部 `220px` の反映前確認で構成します。

- 左 `340px`: 候補グループ、候補枝、未展開の枝、例外の枝置き場
- 中央: 選択した枝の確率、4軸影響、観測、例外
- 右 `330px`: 枝操作ラベル
- 下部: 操作前後の見込みと警告

枝操作ラベル:

- 枝を切る
- 枝を弱める
- 有力枝を残す
- 枝を固定する
- 比率を固定する
- 集中度を固定する

現行の候補木ビューは投影・選択・警告プレビューです。候補木内の `反映前確認` / `反映する` / `元に戻す`、未展開・例外への送信、読みの枝候補から追加するボタンは永続データを変更しません。実データの確率編集、伝播preview適用、枝刈り記録は `詳細編集` またはReasoning Labで行います。

詳細編集ではchoice group、確率、重み、lock mode、分布、伝播preview、scenario compareを扱います。previewを適用するまでworkspaceを変更しません。

### 5.2 影響モデル

指標レンズ、曖昧性パネル、枝ベクトル要約、観測計画を表示します。方向はnodeではなくinfluence edgeの `sign` から読みます。

### 5.3 枝刈りラボ

Reasoning Labをpruning scopeで開きます。枝刈りとロックを別操作として表示し、before / after差分とwarningを確認します。

## 6. 読みを検証する

Reasoning Labを集中度タブから開き、次を切り替えます。

- Graph View
- Metric Lens
- Concentration Lens
- Pruning Lab
- Lock Analysis
- Ambiguity / Observation Planner
- Reading Chain Timeline
- Educational Explanation

派生指標は研究・説明用で、正解率や対局結果を示すものではありません。

## 7. 教材化する

Reasoning Labの説明領域を開き、teaching log、操作差分、読み有用度から説明文を表示します。自動行動推奨は生成しません。

## 8. データ管理

2カラムです。

- 左: workspace JSON、pruning subgraph JSON
- 右 `420px`: テキスト / ファイル取り込み、初期データへ戻す

workspace exportは全体を出力します。subgraph exportは `選択範囲` / `active Sheet` / `active Project` / `Workspace` から対象を選びます。importはzodで検証し、旧v1〜v3またはProject / Sheet未所属のv4を正規化します。

`初期データに戻す` は現在のworkspaceをseedへ置き換える破壊的操作です。重要なデータは実行前にJSON exportします。

## 9. 空・処理・警告状態

- caseがない: `ケースを作成` を表示する。
- スコープ内候補がない: 各panelに空状態文を表示する。
- 保存中: 保存ボタンを無効化し、保存中表示にする。
- import失敗: 取り込みpanelと共通エラー領域へ理由を表示する。
- mixed / unknown、未配分、低確信度、大きな影響、固定中の枝: hard prune前の警告対象にする。
- modal: 背景overlay上へ表示し、内部を縦scroll可能にする。

## 10. アクセシビリティと表示制約

- アイコンだけの主要ボタンには `aria-label` または `title` を付ける。
- 選択型ボタンは必要に応じて `aria-pressed` を使う。
- keyboard shortcutはinput、textarea、select、contenteditable編集中に誤発火させない。
- 現行UIは日本語を主表示とするが、Project、Sheet、Workspace、Reading Probability Coreなどschemaや概念名は英語表記を併用する。
- 固定幅カラムを使う画面はデスクトップ幅を前提とする。狭幅時の完全なresponsive対応は未実装である。

## 11. 関連文書

- [要件定義書](./requirements-definition.md)
- [詳細仕様書](./detailed-specification.md)
- [ユーザー向け仕様書](./specification.md)
- [アーキテクチャ](./architecture.md)
- [スキーマ](./schema.md)
