# Focused Pruning Canvas

## 起動

この作業環境では、Windows PowerShellで次を実行します。

```powershell
cd "C:\Users\weath\Documents\プルーニングUI\focused-pruning-canvas"
npm start
```

ブラウザで **http://127.0.0.1:5174/** を開きます。起動中はPowerShellを開いたままにし、終了するときは `Ctrl+C` を押します。通常の起動で毎回 `npm install` は不要です。

**`Port 5174 is already in use` が出た場合**は、まず上記URLを開いてください。Focused Pruning Canvasが表示されれば起動済みなので、そのまま使えます。再起動する場合は、先に起動したターミナルで `Ctrl+C` を押してから `npm start` を実行します。

## アプリについて

競合仮説・成立条件・薄まり理由を、一画面で編集して比較するローカルアプリです。日本語の考察用で、実戦中の支援は対象外です。相対配分は仮置き重みによる未校正のモデル値で、実測確率・麻雀の正解・押し引き推奨ではありません。

## 起動環境・初回セットアップ

既存アプリと別のパッケージです。既存アプリのフォルダから、Windows PowerShell / Linux ともに次を実行します。

```sh
cd focused-pruning-canvas
npm start
```

ブラウザで **http://127.0.0.1:5174/** を開きます。localhost のみにバインドし、LANには公開しません。通常の起動で毎回インストールは不要です。

この作業環境では親フォルダの既存依存を使用できます。独立した場所への初回配置や再現環境では、このパッケージの `package-lock.json` を使います。

```sh
npm ci
npx playwright install chromium
npm start
```

検証に使用した Node は **22.19.0**、npm は **11.5.2**。パッケージの互換条件は `package.json` の `engines`、全依存の固定値は lockfile が正本です。オフライン環境で npm ci に必要なキャッシュがない場合は、依存取得が必要です。検証環境と未確認事項は [検証記録](docs/verification.md) を参照してください。

## 最初に試す操作

1. 初期モデルの本線 H1（約58.2%）と、保護された H2・残余 H5 を比較します。H3はH4のリャンカン由来を含めない仮分類です。
2. H2を選択して、右側の「なぜ薄いか」「同根抑制」「何なら復活するか」「寄与台帳」「根拠原文」を確認します。
3. 左の要因「聴牌している」を選び、状態を「あり」にして「要因の変更を保存」。続いて「3飜以上の高打点が見込める」も「あり」にします。H2が上昇し、安手非聴牌の減点が適用外になります。
4. 下の操作履歴、Undo、Redoを試します。再読込後も文書と履歴・cursorを復元します。
5. 「新規」で空のBoardを作成し、問いを編集します。アウトラインの＋で仮説・要因を追加し、要因の「仮説への接続を追加」で強度・状態・同根グループを設定します。
6. 仮説の横の＋で説明メモを作成します。子メモ、字下げ・字上げ、親メモの選択が使えます。説明の階層だけではスコアは変わりません。
7. JSONまたはMarkdownでexportし、「読込」で復元を確認します。import前には現在の内容を退避できます。

標準表示は選択仮説の関係を展開します。「結論」は主要な枝だけ、「全展開」は全接続を表示します。カードの位置は配分順に並べ替えません。拡大縮小・全体表示はCanvas左下です。ウィンドウ幅を変えて枝が画面外になったときも「全体を表示」を使います。1280px以下では上部のアウトライン／インスペクター切替を利用してください。

## 編集とキーボード

フォームは保存ボタンで確定します。入力中はドラフトで、文字ごとの履歴や保存を行いません。

- アウトラインのラベルをダブルクリック、または鉛筆ボタンで編集。Enterで確定と同種の兄弟追加を一操作にし、Escapeで取り消します。空ラベルは確定しません。
- 「メモの構造編集」をONにしたときだけ、メモ行のTabで直前の兄弟の子へ、Shift+Tabで字上げします。Escapeで構造編集を終了。通常Tabはフォーカス移動です。
- 選択行のCtrl/Cmd+Deleteで参照関係付きの削除確認。文字編集中は通常の文字削除です。
- Ctrl/Cmd+ZでUndo、Ctrl/Cmd+Shift+ZまたはCtrl+YでRedo。テキスト編集中はブラウザの文字編集Undoを優先します。
- 日本語IMEの変換中はEnter/Tabを追加コマンドへ流しません。自動検証は合成イベントで、実IMEの手動検証済みという意味ではありません。

実IMEの手動確認手順：Microsoft IME等をONにしてラベルを編集し、「りゃんめん」を変換中にEnterで変換確定します。この段階で項目数・履歴が増えないこと、その後の通常Enterでは兄弟が一つだけ増えること、Escapeで取り消せることを確認してください。メモの構造編集のON/OFFでTabの行き先も確認します。

保護・残余枝はpruneと削除ができません。保護は配分の下限保証ではなく、確認済みhard不成立なら配分0のカードを残します。「弱める」は手動調整を−1へ設定する冪等操作、「復元」はprune解除と手動調整0を一操作で行います。

## 保存とファイル

ブラウザの本アプリ専用キー `focused-pruning-canvas.v1` に、確定操作ごとに同期保存します。保存成功時のみ「保存済み」と表示します。**ブラウザのデータ削除や別のoriginへの移動では復元できないため、JSONをバックアップしてください。** 既存アプリのIndexedDBや他アプリのStorageは操作しません。

履歴はflatなsnapshot列とcursorです。保存対象は最大50件、UTF-8でEnvelope 2MiB内の直近履歴。編集による超過では古い履歴から短縮して通知し、現在の本文は切りません。Board単体512KiB、入力ファイル5MiB、原文合計64,000文字などの境界も検証します。永久監査ログではありません。全上限は [仕様](docs/spec.md) 第15節に記載しています。

破損・未対応versionなら自動保存を止め、raw退避・再試行・明示的復旧を表示します。容量不足・アクセス拒否時は編集をメモリに保持して未保存を示し、JSON退避と保存再試行を提供します。別タブ更新の検出時も保存を止めます。書込直前に前回読込／保存値（revisionを含む）を照合しますが、完全な排他制御ではありません。同時競合の解消や共同編集は対象外です。

JSONは文書・履歴・cursor・設定・原文を含む復元用正本です。専用Markdownは人間向け概要と、厳密に一つの `pruning-ui-json` blockを含みます。**Markdown本文の編集は復元に反映されず、埋込データが正本です。** 一般Markdownの文章解析は行いません。importは全snapshotを検証し、確認後にファイルの履歴へ置き換えます。失敗／キャンセルでは現行データを変更せず、適用後に保存が失敗した場合はimport前の状態に戻せます。revisionだけはローカル保存時に更新します。

## コマンド

| コマンド                                  | 内容                                           |
| ----------------------------------------- | ---------------------------------------------- |
| `npm start` / `npm run dev`               | localhost開発サーバ                            |
| `npm run typecheck`                       | アプリ・テスト・設定のstrict型検査             |
| `npm run lint`                            | ESLint                                         |
| `npm run format:check` / `npm run format` | Prettier確認 / 修正                            |
| `npm test` / `npm run test:watch`         | Vitest一回 / watch                             |
| `npm run test:e2e`                        | Playwright Chromium                            |
| `npm run build` / `npm run preview`       | 本番ビルド / localhost:4174で確認              |
| `npm run check`                           | typecheck → lint → format:check → test → build |

UI検証画像は `test-results/canvas-1440x900.png` と `test-results/canvas-1280x800.png`。失敗時のtraceと画像も `test-results/` に残し、Git対象には含めません。利用者向けPNG export機能とは別です。

## 構成と継続開発

`src/domain` はReact非依存のZod契約・純粋計算・検証・コマンド・説明・差分、`src/application` は履歴と保存port、`src/infrastructure` はStorageとファイル境界、`src/features` は画面、`src/app` は具象の組立です。`src/shared/styles` は基本、画面配置、Canvas、InspectorのCSSに分けています。

正本は [仕様](docs/spec.md)、[受入条件・対応表](docs/acceptance.md)、[実行計画](docs/exec-plan.md)。[原文](docs/source-material.md)、[設計判断](docs/design-decisions.md)、[参照レビュー](docs/reference-review.md)、[変更監査](docs/change-audit.md)も保全しています。

公開やpushは利用者から依頼された場合に行います。このサブディレクトリの `.github/workflows/ci.yml` は独立配置時の最小CI設定です。現在の親リポジトリでは入れ子のworkflowをGitHubが実行しないため、CI実行は未確認です。

## 非対象・次の候補

認証、クラウド、外部API、LLM、自動文章解析、Project/Sheet、EV・押し引き推奨はありません。条件木はプリセット表示と要因編集・import対応までで、高機能な任意条件ツリーGUIや階層ごとの確率伝播は実装していません。

次の候補は、複数の競合仮説群、任意の条件GUI、利用者向けPDF/PNG/SVG出力です。対象化する場合は先に仕様と受入IDを追加します。
